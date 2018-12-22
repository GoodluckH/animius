import tensorflow as tf
import numpy as np


class CombinedPredictionModel:

    # For some reason using the optimized model fails.
    # Use the frozen one instead.
    # ALso, graph transform seems to perform worse than the frozen model...
    def __init__(self, restore_graph):

        # restore graph
        graph_def = tf.GraphDef()
        with tf.gfile.Open(restore_graph, "rb") as f:
            graph_def.ParseFromString(f.read())

        graph = tf.Graph()
        with graph.as_default():
            tf.import_graph_def(graph_def)

        # init tensorflow
        config = tf.ConfigProto()
        config.gpu_options.allow_growth = True
        self.sess = tf.Session(config=config, graph=graph)

    def intent_predict(self, input_data, save_path=None):
        intent, ner = self.sess.run([self.sess.graph.get_tensor_by_name('intent/output_intent:0'),
                                     self.sess.graph.get_tensor_by_name('intent/output_ner:0')],
                                    feed_dict={
                                        'intent/input_x:0': input_data.values['x'],
                                        'intent/input_x_length:0': input_data.values['x_length']
                                    })

        ner = [ner[i, :int(input_data.values['x_length'][i])] for i in range(len(ner))]

        if save_path is not None:
            with open(save_path, "w") as file:
                for i in range(len(intent)):
                    file.write(str(intent[i]) + ' - ' + ', '.join(str(x) for x in ner[i]) + '\n')

        return intent, ner

    def chatbot_predict(self, input_data, save_path=None):
        test_output = self.sess.run(self.sess.get_tensor_by_name('decode_1/output_infer:0'),
                                    feed_dict={
                                        'input_x:0': input_data.values['x'],
                                        'input_x_length:0': input_data.values['x_length']
                                    })
        # Beam
        list_res = []
        for batch in test_output:
            result = []
            for beam in batch:  # three branches
                beam_res = ''
                for index in beam:
                    # if test_output is a numpy array, use np.take
                    # append the words into a sentence
                    beam_res = beam_res + input_data['embedding'].words[int(index)] + " "
                result.append(beam_res)
            list_res.append(result)

        if save_path is not None:
            with open(save_path, "w") as file:
                for i in range(len(list_res)):
                    file.write(str(list_res[i][0]) + '\n')

        return list_res

    def predict(self, input_data):

        intent, ner = self.intent_predict(input_data)
        # intent = [batch, intents], ner = [batch, words, entities]

        intent_argmax = np.argmax(intent, axis=-1)

        result = []
        chat_indexes = []

        for i in range(len(intent_argmax)):
            if intent_argmax[i] > 0:  # user query
                result.append((intent_argmax[i], np.argmax(ner[i], axis=-1).tolist()))
            else:  # casual chat
                chat_indexes.append(i)  # save index to predict at once for optimization

        if len(chat_indexes) > 0:
            chat_input = input_data.get_chatbot_input(chat_indexes)
            chat = self.chatbot_predict(chat_input)  # [batch, beam]
            chat = chat[:, 0]

            for i in chat:
                result.append((0, i))

        return result
