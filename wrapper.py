"""
Wrapper class.

Based on https://github.com/Hironsan/anago
"""
from seqeval.metrics import f1_score

from load_data import load_data
from models import BiLSTMCRF, save_model, load_model
from preprocessing import VectorTransformer
from trainer import Trainer

import os


class Sequence(object):
    def __init__(self,
                 embedding,
                 char_embedding_dim=25,
                 word_lstm_size=100,
                 char_lstm_size=25,
                 fc_dim=100,
                 dropout=0.5,
                 use_char=True,
                 use_crf=True,
                 initial_vocab=None,
                 lower=False,
                 optimizer='adam',
                 nn_type='GRU'):

        self.model = None
        self.tagger = None

        self.p = VectorTransformer(embedding, use_char=use_char)

        self.char_embedding_dim = char_embedding_dim
        self.word_lstm_size = word_lstm_size
        self.char_lstm_size = char_lstm_size
        self.fc_dim = fc_dim
        self.dropout = dropout
        self.use_char = use_char
        self.use_crf = use_crf
        self.initial_vocab = initial_vocab
        self.optimizer = optimizer
        self.lower = lower
        self.nn_type = nn_type

    def fit(self, x_train, y_train, x_valid=None, y_valid=None,
            epochs=1, batch_size=32, verbose=1, callbacks=None, shuffle=True):
        """Fit the model for a fixed number of epochs.

        Args:
            x_train: list of training model.
            y_train: list of training target (label) model.
            x_valid: list of validation model.
            y_valid: list of validation target (label) model.
            batch_size: Integer.
                Number of samples per gradient update.
                If unspecified, `batch_size` will default to 32.
            epochs: Integer. Number of epochs to train the model.
            verbose: Integer. 0, 1, or 2. Verbosity mode.
                0 = silent, 1 = progress bar, 2 = one line per epoch.
            callbacks: List of `keras.callbacks.Callback` instances.
                List of callbacks to apply during training.
            shuffle: Boolean (whether to shuffle the training model
                before each epoch). `shuffle` will default to True.
        """

        self.p.fit(x_train, y_train)

        model = BiLSTMCRF(num_labels=self.p.label_size,
                          word_embedding_dim=self.p.vector_len,
                          word_lstm_size=self.word_lstm_size,
                          char_lstm_size=self.char_lstm_size,
                          fc_dim=self.fc_dim,
                          dropout=self.dropout,
                          use_char=self.use_char,
                          use_crf=self.use_crf,
                          nn_type=self.nn_type)
        model, loss = model.build()

        model.compile(loss=loss, optimizer=self.optimizer)

        trainer = Trainer(model, preprocessor=self.p)
        trainer.train(x_train, y_train, x_valid, y_valid,
                      epochs=epochs, batch_size=batch_size,
                      verbose=verbose, callbacks=callbacks,
                      shuffle=shuffle)
        if x_train and y_valid:
            self.model = trainer.best_model
            self.best_report = trainer.best_model_report
            print("Best model report: ")
            print(self.best_report)

    def score(self, x_test, y_test):
        """Returns the f1-micro score on the given test model and labels.

        Args:
            x_test : array-like, shape = (n_samples, sent_length)
            Test samples.

            y_test : array-like, shape = (n_samples, sent_length)
            True labels for x.

        Returns:
            score : float, f1-micro score.
        """
        if self.model:
            x_test = self.p.transform(x_test)
            lengths = map(len, y_test)
            y_pred = self.model.predict(x_test)
            y_pred = self.p.inverse_transform(y_pred, lengths)
            score = f1_score(y_test, y_pred)
            return score
        else:
            raise OSError('Could not find a model. Call load(dir_path).')

    def predict_to_iob(self, input_path, output_path):
        output_file = open(output_path, 'w')
        x, _, all_ctags = load_data(input_path)

        for sentence, sent_ctags in zip(x, all_ctags):
            predictions = self.predict_sentence(sentence)
            for token, prediction, ctags in zip(sentence, predictions, sent_ctags):
                to_write = token
                for ctag in ctags:
                    to_write += ' ' + ctag
                if prediction != '':
                    to_write += ' ' + prediction
                else:
                    to_write += ' O\n'
                output_file.write(to_write)
            output_file.write('\n')
                
    def predict_sentence(self, sentence):
        x_test = self.p.transform([sentence])
        lengths = [len(sentence)]
        y_pred = self.model.predict(x_test)
        y_pred = self.p.inverse_transform(y_pred, lengths)
        #print(y_pred)
        return y_pred[0]

    def save(self, model_path):
        weights_file = os.path.join(model_path, "weights.pkl")
        params_file = os.path.join(model_path, "params.pkl")
        preprocessor_file = os.path.join(model_path, "preprocessor.pkl")
        self.p.save(preprocessor_file)
        save_model(self.model, weights_file, params_file)

    @classmethod
    def load(cls, model_path, embedding_object):
        weights_file = os.path.join(model_path, "weights.pkl")
        params_file = os.path.join(model_path, "params.pkl")
        preprocessor_file = os.path.join(model_path, "preprocessor.pkl")
        self = cls(embedding_object)
        self.model = load_model(weights_file, params_file)
        self.p = VectorTransformer.load(preprocessor_file, embedding_object)
        return self

