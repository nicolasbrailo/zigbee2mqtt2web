import logging
logger = logging.getLogger('zigbee2mqtt2flask.thing')

import sqlite3

class SensorsDB:
    def __init__(self, dbpath, table, metrics, retention_rows=-1):
        self.retention_rows = retention_rows
        self.table_name = table
        self.metrics = metrics
        self.conn = sqlite3.connect(dbpath)
        self.maybe_create_tables()

    def maybe_create_tables(self):
        metric_cols = " REAL, ".join(self.metrics)
        self.conn.execute(
                f"CREATE TABLE IF NOT EXISTS {self.table_name} ("\
                "  sensor_name TEXT NOT NULL, "\
                "  sample_time DATETIME DEFAULT CURRENT_TIMESTAMP, "\
                f"  {metric_cols}"\
                ")")

    def get_schema(self):
        return ['rowid', 'sensor_name', 'sample_time'] + self.metrics

    def get_all(self):
        return self.conn.execute(f"SELECT rowid, * FROM {self.table_name}")\
                   .fetchall()

    def print_debug(self):
        print(db.get_schema())
        for s in db.get_all():
            print(s)

    def add_sample(self, s):
        if not hasattr(s, 'sensor_name'):
            raise TypeError(f"{s.__class__.__name__} must have attribute 'sensor_name'")

        cols = ['sensor_name']
        vals = [s.sensor_name]

        for m in self.metrics:
            if hasattr(s, m):
                cols.append(m)
                vals.append(getattr(s, m))

        cols_q = ", ".join(cols)
        vals_placeholders = ", ".join('?' * len(cols))
        q = f"INSERT INTO {self.table_name}"\
            f" ({cols_q}) VALUES ({vals_placeholders})"

        self.conn.execute(q, vals)
        self.discard_old_samples()
        self.conn.commit()

    def discard_old_samples(self):
        if self.retention_rows is None or self.retention_rows <= 0:
            return

        self.conn.execute(\
            f"DELETE FROM {self.table_name} "\
            f"WHERE rowid NOT IN ("\
            f"  SELECT ROWID FROM samples "\
            f"  ORDER BY sample_time DESC "\
            f"  LIMIT {self.retention_rows} "\
            f")"\
        )

