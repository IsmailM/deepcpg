#!/usr/bin/env python

import argparse
import sys
import logging
import os.path as pt
import pandas as pd
import numpy as np

from predict.models.dnn.utils import read_labels, open_hdf, load_model, write_z, ArrayView


class App(object):

    def run(self, args):
        name = pt.basename(args[0])
        parser = self.create_parser(name)
        opts = parser.parse_args(args[1:])
        self.opts = opts
        return self.main(name, opts)

    def create_parser(self, name):
        p = argparse.ArgumentParser(
            prog=name,
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            description='Make prediction on data set')
        p.add_argument(
            'data_file',
            help='Data file')
        p.add_argument(
            'model_file',
            help='Model json file')
        p.add_argument(
            'model_weights_file',
            help='Model weights file')
        p.add_argument(
            '-o', '--out_file',
            help='Output file')
        p.add_argument(
            '--batch_size',
            help='Batch size',
            type=int,
            default=1024)
        p.add_argument(
            '--nb_sample',
            help='Maximum # training samples',
            type=int)
        p.add_argument(
            '--max_mem',
            help='Maximum memory load',
            type=int,
            default=14000)
        p.add_argument(
            '--seed',
            help='Seed of rng',
            type=int,
            default=0)
        p.add_argument(
            '--verbose',
            help='More detailed log messages',
            action='store_true')
        p.add_argument(
            '--log_file',
            help='Write log messages to file')
        return p

    def main(self, name, opts):
        logging.basicConfig(filename=opts.log_file,
                            format='%(levelname)s (%(asctime)s): %(message)s')
        log = logging.getLogger(name)
        if opts.verbose:
            log.setLevel(logging.DEBUG)
        else:
            log.setLevel(logging.INFO)
            log.debug(opts)

        if opts.seed is not None:
            np.random.seed(opts.seed)
        pd.set_option('display.width', 150)

        log.info('Load model')
        model = load_model(opts.model_file, opts.model_weights_file)

        log.info('Load data')
        def read_data(path):
            f = open_hdf(path, cache_size=opts.max_mem)
            data = dict()
            for k, v in f['data'].items():
                data[k] = v
            for k, v in f['pos'].items():
                data[k] = v
            return (f, data)

        labels = read_labels(opts.data_file)
        data_file, data = read_data(opts.data_file)

        def to_view(d):
            for k in d.keys():
                d[k] = ArrayView(d[k], stop=opts.nb_sample)

        to_view(data)
        log.info('%d samples' % (list(data.values())[0].shape[0]))

        def progress(batch, nb_batch):
            batch += 1
            c = max(1, int(np.ceil(nb_batch / 50)))
            if batch == 1 or batch == nb_batch or batch % c == 0:
                print('%5d / %d (%.1f%%)' % (batch, nb_batch,
                                             batch / nb_batch * 100))

        batch_size = opts.batch_size
        if batch_size is None:
            if 'c_x' in model.input_order and 's_x' in model.input_order:
                batch_size = 768
            elif 's_x' in model.input_order:
                batch_size = 1024
            else:
                batch_size = 2048

        log.info('Predict')
        z = model.predict(data, verbose=opts.verbose,
                          callbacks=[progress],
                          batch_size=opts.batch_size)
        log.info('Write')
        write_z(data, z, labels, opts.out_file)

        data_file.close()
        log.info('Done!')

        return 0


if __name__ == '__main__':
    app = App()
    app.run(sys.argv)
