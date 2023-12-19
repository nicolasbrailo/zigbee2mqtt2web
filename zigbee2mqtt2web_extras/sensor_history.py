""" Keeps a historical database of sensor readings """

import sqlite3
import logging
logger = logging.getLogger(__name__)


def _maybe_create_table(conn, sensor_name, metrics):
    metric_cols = ' REAL, '.join(metrics)
    conn.execute(
        f'CREATE TABLE IF NOT EXISTS {sensor_name} ('
        '   sample_time DATETIME DEFAULT CURRENT_TIMESTAMP, '
        f'  {metric_cols}'
        ')')


def _discard_old_samples_by_retention_count(conn, sensor_name, retention_rows):
    if retention_rows is None or retention_rows <= 0:
        return
    conn.execute(
        f'DELETE FROM {sensor_name} '
        f'WHERE '
        f'  rowid NOT IN ('
        f'    SELECT ROWID FROM {sensor_name} '
        f'    ORDER BY sample_time DESC '
        f'    LIMIT {retention_rows} '
        f'  )'
    )


def _discard_old_samples_by_retention_days(conn, sensor_name, retention_days):
    if retention_days is None:
        return
    conn.execute(
        f"DELETE FROM {sensor_name} "
        f"WHERE sample_time < datetime('now', '-{retention_days} days')"
    )


def _get_known_sensors(conn):
    res = conn.execute(
        "SELECT name FROM sqlite_schema WHERE type = 'table'").fetchall()
    # unpack, so we return as a vector instead of a vec of tuples
    return [x for (x,) in res]


def _get_sensor_metrics(conn, sensor_name):
    res = conn.execute(f"SELECT name FROM PRAGMA_TABLE_INFO('{sensor_name}')")
    # unpack, so we return as a vector instead of a vec of tuples
    # also remove the special metric "sample_time"
    return [metric for (metric,) in res.fetchall() if metric != 'sample_time']


def _sensors_with_metric(conn, metric):
    all_sensors = []
    for sensor_name in _get_known_sensors(conn):
        if metric in _get_sensor_metrics(conn, sensor_name):
            all_sensors.append(sensor_name)
    return all_sensors


def _csv(header, data):
    csv = ','.join(header) + '\n'
    for row in data:
        csv += ','.join(str(x) for x in row) + '\n'
    return csv


class SensorsHistory:
    """ Automatically hooks up an observer to a sensor-like thing, and keeps
    track of changes in the sensor so it can save the change history to a DB """

    def __init__(self, dbpath, retention_rows=None, retention_days=None):
        self._retention_rows = retention_rows
        self._retention_days = retention_days
        self._dbpath = dbpath

    def register_to_webserver(self, server):
        """ Will hook this object to a flask-like webserver, so that the sensor
        database is exposed over certain http endpoints """
        server.add_url_rule('/sensors/ls', self.get_known_sensors)
        server.add_url_rule(
            '/sensors/get_all_metrics_in_sensor_csv/<sensor_name>',
            self.get_all_metrics_in_sensor_csv)
        server.add_url_rule(
            '/sensors/get_single_metric_in_all_sensors_csv/<metric>',
            self.get_single_metric_in_all_sensors_csv)

    def register_sensor(self, thing, metrics):
        """ Will attach an observer to $thing and save a reading to a database
        whenever $thing has an updated value """
        for metric in metrics:
            if metric not in thing.actions:
                raise KeyError(f'Thing {thing.name} has no metric {metric}. Available actions: {thing.actions.keys()}')

        if thing.on_any_change_from_mqtt is not None:
            raise AttributeError(
                f'Thing {thing.name} already has an observer')

        thing.on_any_change_from_mqtt = lambda: self._on_update(thing, metrics)
        logger.info('Registered sensor %s to sensor_history', thing.name)

    def _on_update(self, thing, metrics):
        logger.debug('Sensor %s has an update, will save to DB', thing.name)
        readings = [thing.get(metric_name) for metric_name in metrics]

        conn = sqlite3.connect(self._dbpath)
        _maybe_create_table(conn, thing.name, metrics)

        cols_q = ', '.join(metrics)
        vals_placeholders = ', '.join('?' * len(metrics))
        query = f'INSERT INTO {thing.name}'\
                f' ({cols_q}) VALUES ({vals_placeholders})'
        conn.execute(query, readings)

        _discard_old_samples_by_retention_count(
            conn, thing.name, self._retention_rows)
        _discard_old_samples_by_retention_days(
            conn, thing.name, self._retention_days)
        conn.commit()

    def get_known_sensors(self):
        """ Returns a list of all sensor names kept in this database """
        return _get_known_sensors(sqlite3.connect(self._dbpath))

    def get_all_metrics_in_sensor_csv(self, sensor_name):
        """ Equivalent to select * for a single sensor: retrieves all historical
        data for a single sensor, as far as the retention period allows """
        conn = sqlite3.connect(self._dbpath)
        if sensor_name not in _get_known_sensors(conn):
            logger.error('Received request for unknown sensor %s', sensor_name)
            return ''

        metrics = _get_sensor_metrics(conn, sensor_name)
        cols = ','.join(metrics)
        query = f"SELECT sample_time, {cols} FROM {sensor_name} ORDER BY sample_time"
        res = conn.execute(query).fetchall()
        return _csv(['sample_time'] + metrics, res)

    def get_single_metric_in_all_sensors_csv(self, metric):
        """ Gets the same metric, as measured by different sensors. Will check
        on all known sensors (sensors that don't know this metric will be skipped """
        conn = sqlite3.connect(self._dbpath)

        all_sensors = _sensors_with_metric(conn, metric)
        if len(all_sensors) == 0:
            return ''

        # Select a single column per sensor (=table), and enough nulls for all
        # other columns. The query should look like
        # SELECT * FROM (
        #   SELECT metric AS sensor1, NULL as sensor2,   NULL as sensor3...
        #   UNION
        #   SELECT NULL AS sensor1,   metric as sensor2, NULL as sensor3...
        #   UNION
        #   SELECT NULL AS sensor1,   NULL as sensor2,   metric as sensor3...
        #   UNION
        #   ...
        # )
        sensor_qs = []
        for sensor in all_sensors:
            cols_mask = []
            for other_sensor in all_sensors:
                if other_sensor == sensor:
                    cols_mask.append(f"{metric} AS {sensor}")
                else:
                    cols_mask.append(f"'' AS {other_sensor}")
            cols = ", ".join(cols_mask)
            sensor_qs.append(f"SELECT sample_time, {cols} "
                             f"FROM {sensor} "
                             f"WHERE {metric} IS NOT NULL")

        query = "SELECT * FROM (" +\
                (" UNION ".join(sensor_qs)) +\
                ") ORDER BY sample_time"
        res = conn.execute(query).fetchall()
        return _csv(['sample_time'] + all_sensors, res)
