import logging
logger = logging.getLogger('zigbee2mqtt2flask.thing')

import sqlite3

class SensorsDB:
    def __init__(self, dbpath, metrics, retention_rows=-1):
        self.retention_rows = retention_rows
        self.metrics = metrics
        self.dbpath = dbpath

    def register_flask(self, flask_app):
        @flask_app.route('/sensors/ls')
        def sensors_ls():
            return self.get_known_sensors()

        @flask_app.route('/sensors/get_all_metrics_in_sensor_csv/<sensor_name>')
        def get_all_metrics_in_sensor_csv(sensor_name):
            return self.get_all_metrics_in_sensor_csv(sensor_name)

        @flask_app.route('/sensors/get_single_metric_in_all_sensors_csv/<metric>')
        def get_single_metric_in_all_sensors_csv(metric):
            return self.get_single_metric_in_all_sensors_csv(metric)

    def _csv(self, header, data):
        csv = ','.join(header) + '\n'
        for row in data:
            csv += ','.join(str(x) for x in row) + '\n'
        return csv

    def get_known_sensors(self):
        conn = sqlite3.connect(self.dbpath)
        res = conn.execute("SELECT name FROM sqlite_schema WHERE type = 'table'")\
                  .fetchall()
        # unpack, so we return as a vector instead of a vec of tuples
        return [x for (x,) in res]

    def add_sample(self, s):
        if not hasattr(s, 'sensor_name'):
            raise TypeError(f"{s.__class__.__name__} must have attribute 'sensor_name'")

        conn = sqlite3.connect(self.dbpath)
        self._maybe_create_table(conn, s.sensor_name)

        cols = []
        vals = []
        for m in self.metrics:
            if hasattr(s, m):
                cols.append(m)
                vals.append(getattr(s, m))

        cols_q = ", ".join(cols)
        vals_placeholders = ", ".join('?' * len(cols))
        q = f"INSERT INTO {s.sensor_name}"\
            f" ({cols_q}) VALUES ({vals_placeholders})"
        conn.execute(q, vals)

        self._discard_old_samples(conn, s.sensor_name)
        conn.commit()

    def _maybe_create_table(self, conn, sensor_name):
        metric_cols = " REAL, ".join(self.metrics)
        conn.execute(
                f"CREATE TABLE IF NOT EXISTS {sensor_name} ("\
                "  sample_time DATETIME DEFAULT CURRENT_TIMESTAMP, "\
                f"  {metric_cols}"\
                ")")

    def _discard_old_samples(self, conn, sensor_name):
        if self.retention_rows is None or self.retention_rows <= 0:
            return
        conn.execute(\
            f"DELETE FROM {sensor_name} "\
            f"WHERE "\
            f"  rowid NOT IN ("\
            f"    SELECT ROWID FROM {sensor_name} "\
            f"    ORDER BY sample_time DESC "\
            f"    LIMIT {self.retention_rows} "\
            f"  )"\
        )

    def get_single_metric_in_all_sensors_csv(self, metric):
        if metric not in self.metrics:
            logger.error(f"Received request for unknown metric {metric}")
            return ''

        all_sensors = self.get_known_sensors()
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
            sensor_qs.append(f"SELECT sample_time, {cols} "\
                             f"FROM {sensor} "\
                             f"WHERE {metric} IS NOT NULL")

        q = "SELECT * FROM (" +\
                (" UNION ".join(sensor_qs)) +\
            ") ORDER BY sample_time"
        res = sqlite3.connect(self.dbpath).execute(q).fetchall()

        return self._csv(['sample_time'] + all_sensors, res)

    def get_all_metrics_in_sensor_csv(self, sensor):
        if sensor not in self.get_known_sensors():
            logger.error(f"Received request for unknown sensor {sensor}")
            return ''

        cols = ','.join(self.metrics)
        q = f"SELECT sample_time, {cols} FROM {sensor} ORDER BY sample_time"
        res = sqlite3.connect(self.dbpath).execute(q).fetchall()

        return self._csv(['sample_time'] + self.metrics, res)

