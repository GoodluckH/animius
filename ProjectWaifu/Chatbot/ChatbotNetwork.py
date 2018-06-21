import tensorflow as tf
import numpy as np
from ProjectWaifu.Network import Network
import ProjectWaifu.Chatbot.ParseData as ParseData
import ProjectWaifu.WordEmbedding as WordEmbedding
from ProjectWaifu.Utils import get_mini_batches


class ChatbotNetwork(Network):

    def __init__(self, learning_rate=0.001, batch_size=16, restore=False):
        # hyperparameters
        self.learning_rate = learning_rate
        self.batch_size = batch_size

        # Network hyperparameters
        self.n_vector = len(WordEmbedding.embeddings[0])
        self.word_count = len(WordEmbedding.words)
        self.max_sequence = 20
        self.n_hidden = 128

        # Tensorflow placeholders
        self.x = tf.placeholder(tf.int32, [None, self.max_sequence])
        self.x_length = tf.placeholder(tf.int32, [None])
        self.y = tf.placeholder(tf.int32, [None, self.max_sequence])
        self.y_length = tf.placeholder(tf.int32, [None])
        self.word_embedding = tf.Variable(tf.constant(0.0, shape=(self.word_count, self.n_vector)), trainable=False)

        # Network parameters
        def get_gru_cell():
            return tf.contrib.rnn.GRUCell(self.n_hidden)

        self.cell_encode = tf.contrib.rnn.MultiRNNCell([get_gru_cell() for _ in range(3)])
        self.cell_decode = tf.contrib.rnn.MultiRNNCell([get_gru_cell() for _ in range(3)])
        self.projection_layer = tf.layers.Dense(self.word_count)

        # Optimization
        dynamic_max_sequence = tf.reduce_max(self.y_length)
        mask = tf.sequence_mask(self.y_length, maxlen=dynamic_max_sequence, dtype=tf.float32)
        # crossent = tf.nn.sparse_softmax_cross_entropy_with_logits(
        #     labels=self.y[:, :dynamic_max_sequence], logits=self.network())
        # self.cost = tf.reduce_sum(crossent * mask)
        self.cost = tf.contrib.seq2seq.sequence_loss(self.network(), self.y[:, :dynamic_max_sequence], weights=mask)
        self.train_op = tf.train.AdamOptimizer(self.learning_rate).minimize(self.cost)
        self.infer = self.network(mode="infer")

        # Tensorflow initialization
        self.saver = tf.train.Saver()
        self.sess = tf.Session()
        self.sess.run(tf.global_variables_initializer())

        if restore is False:
            embedding_placeholder = tf.placeholder(tf.float32, shape=WordEmbedding.embeddings.shape)
            self.sess.run(self.word_embedding.assign(embedding_placeholder),
                          feed_dict={embedding_placeholder: WordEmbedding.embeddings})
        else:
            self.saver.restore(self.sess, tf.train.latest_checkpoint('./model'))

    def network(self, mode="train"):

        embedded_x = tf.nn.embedding_lookup(self.word_embedding, self.x)

        encoder_outputs, encoder_state = tf.nn.dynamic_rnn(
            self.cell_encode,
            inputs=embedded_x,
            dtype=tf.float32,
            sequence_length=self.x_length)

        attention_mechanism = tf.contrib.seq2seq.BahdanauAttention(
            num_units=self.n_hidden, memory=encoder_outputs,
            memory_sequence_length=self.x_length)

        attn_decoder_cell = tf.contrib.seq2seq.AttentionWrapper(
            self.cell_decode, attention_mechanism, attention_layer_size=self.n_hidden)

        decoder_initial_state = attn_decoder_cell.zero_state(dtype=tf.float32, batch_size=tf.shape(self.x)[0]).clone(cell_state=encoder_state)

        if mode == "train":

            with tf.variable_scope('decode'):

                embedded_y = tf.nn.embedding_lookup(self.word_embedding, self.y)

                train_helper = tf.contrib.seq2seq.TrainingHelper(
                    inputs=embedded_y,
                    sequence_length=self.y_length
                )

                decoder = tf.contrib.seq2seq.BasicDecoder(
                    attn_decoder_cell,
                    train_helper,
                    decoder_initial_state,
                    output_layer=self.projection_layer
                )

                outputs, _, _ = tf.contrib.seq2seq.dynamic_decode(decoder, maximum_iterations=self.max_sequence, impute_finished=True)

                return outputs.rnn_output
        else:

            with tf.variable_scope('decode', reuse=True):

                # Greedy search
                infer_helper = tf.contrib.seq2seq.GreedyEmbeddingHelper(self.word_embedding, tf.tile(tf.constant([WordEmbedding.start], dtype=tf.int32), [tf.shape(self.x)[0]]), WordEmbedding.end)

                decoder = tf.contrib.seq2seq.BasicDecoder(
                    attn_decoder_cell,
                    infer_helper,
                    decoder_initial_state,
                    output_layer=self.projection_layer
                )

                outputs, _, _ = tf.contrib.seq2seq.dynamic_decode(decoder, maximum_iterations=self.max_sequence,
                                                                  impute_finished=True)

                return outputs.sample_id

                # Beam search
                # beam_width = 3
                # encoder_outputs_beam = tf.contrib.seq2seq.tile_batch(encoder_outputs, beam_width)
                # encoder_state_beam = tf.contrib.seq2seq.tile_batch(encoder_state, beam_width)
                # batch_size_beam = tf.shape(encoder_outputs_beam)[0]
                #
                # attention_mechanism = tf.contrib.seq2seq.BahdanauAttention(
                #     num_units=self.n_hidden, memory=encoder_outputs_beam)
                #
                # attn_decoder_cell = tf.contrib.seq2seq.AttentionWrapper(
                #     self.cell_decode, attention_mechanism, attention_layer_size=self.n_hidden)
                #
                # decoder_initial_state = attn_decoder_cell.zero_state(dtype=tf.float32, batch_size=batch_size_beam)
                #
                # decoder = tf.contrib.seq2seq.BeamSearchDecoder(
                #             cell=attn_decoder_cell,
                #             embedding=self.word_embedding,
                #             start_tokens=tf.tile(tf.constant([WordEmbedding.start], dtype=tf.int32), [tf.shape(self.x)[0]]),
                #             end_token=WordEmbedding.end,
                #             initial_state=decoder_initial_state,
                #             beam_width=beam_width,
                #             output_layer=self.projection_layer
                # )
                #
                # outputs, _, _ = tf.contrib.seq2seq.dynamic_decode(decoder, maximum_iterations=self.max_sequence)
                #
                # return tf.transpose(outputs.predicted_ids, perm=[0, 2, 1])  # [batch size, beam width, sequence length]

    def setTrainingData(self, train_x, train_y):
        train_x = ParseData.split_data(train_x)
        train_y = ParseData.split_data(train_y)

        train_x, train_y, x_length, y_length = \
            ParseData.data_to_index(train_x, train_y,
                                    WordEmbedding.words_to_index)

        print("Training data :", len(train_x))

        self.train_x = np.array(train_x)
        self.train_y = np.array(train_y)
        self.train_x_length = np.array(x_length)
        self.train_y_length = np.array(y_length)

    def train(self, epochs=800, display_step=10):
        for epoch in range(epochs):
            mini_batches_x, mini_batches_x_length, mini_batches_y, mini_batches_y_length \
                = get_mini_batches([self.train_x, self.train_x_length, self.train_y, self.train_y_length], self.batch_size)

            # mini_batches_x = [self.train_x]
            # mini_batches_x_length = [self.train_x_length]
            # mini_batches_y = [self.train_y]
            # mini_batches_y_length = [self.train_y_length]

            for batch in range(len(mini_batches_x)):
                batch_x = mini_batches_x[batch]
                batch_x_length = mini_batches_x_length[batch]
                batch_y = mini_batches_y[batch]
                batch_y_length = mini_batches_y_length[batch]

                if epoch % display_step == 0 or display_step == 0:
                    _, cost_value = self.sess.run([self.train_op, self.cost], feed_dict={
                                        self.x: batch_x,
                                        self.x_length: batch_x_length,
                                        self.y: batch_y,
                                        self.y_length: batch_y_length
                                    })

                    print("epoch:", epoch, "- (", batch, "/", len(mini_batches_x), ") -", cost_value)

                else:
                    self.sess.run(self.train_op, feed_dict={
                        self.x: batch_x,
                        self.x_length: batch_x_length,
                        self.y: batch_y,
                        self.y_length: batch_y_length
                    })

    def predict(self, sentence):

        input_x, x_length, _ = ParseData.sentence_to_index(ParseData.split_sentence(sentence.lower()),
                                                           WordEmbedding.words_to_index)

        test_output = self.sess.run(self.infer[0],
                                    feed_dict={
                                        self.x: np.array([input_x]),
                                        self.x_length: np.array([x_length])
                                    })

        result = ""
        for i in range(len(test_output)):
            result = result + WordEmbedding.words[int(test_output[i])] + "(" + str(test_output[i]) + ") "
        return result

        # list_res = []
        # for index in range(len(test_output)):
        #     result = ""
        #     for i in range(len(test_output[index])):
        #         result = result + WordEmbedding.words[int(test_output[index][i])] + " "
        #     list_res.append(result)
        #
        # return list_res

    def predictAll(self, path, save_path=None):
        pass

    def save(self, step=None, meta=True):
        self.saver.save(self.sess, './model/model', global_step=step, write_meta_graph=meta)


# test
# question, response = ParseData.load_cornell(".\\Data\\movie_conversations.txt", ".\\Data\\movie_lines.txt")

question, response = ParseData.load_twitter("./Data/chat.txt")

WordEmbedding.create_embedding(".\\Data\\glove.twitter.27B.100d.txt")

test = ChatbotNetwork(learning_rate=0.0001, restore=True)

test.setTrainingData(question, response)

question = None
response = None

step = 1

while True:

    test.train(1, 1)

    if step > 0:
        test.save(step, False)
    else:
        test.save(step, True)

    step += 1

    print(test.predict("hello"))

    print(test.predict("what's your name"))

    print(test.predict("fuck you"))