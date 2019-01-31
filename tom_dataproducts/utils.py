import csv
import io


def import_spectroscopic_data(data, target):
    stream = io.StringIO(data.read().decode('utf-8'), newline=None)
    data_reader = csv.DictReader(stream, delimiter=' ')
    for datum in enumerate(data_reader):
        print(datum[0])
        print(datum[1])
