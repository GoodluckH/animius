import animius as am
import os
import json


class ArgumentError(Exception):
    pass


class NameAlreadyExistError(Exception):
    pass


class _ConsoleItem:
    def __init__(self, item=None):
        self.item = item

        self.loaded = item is not None

        self.saved_directory = None
        self.saved_name = None


class Console:

    def __init__(self, init_directory=None):

        animius_dir = os.path.dirname(os.path.realpath(__file__))
        self.config_dir = os.path.join(animius_dir, 'user-config.json')

        sub_dirs = {'waifus', 'models', 'model_configs', 'data', 'embeddings'}

        self.models = {}
        self.waifus = {}
        self.model_configs = {}
        self.data = {}
        self.embeddings = {}

        # No config / first time initializing
        if not os.path.exists(self.config_dir):

            if init_directory is None:
                print("Please enter the data directory to save data in:")
                print("Default ({0})".format(os.path.join(animius_dir, 'resources')))
                init_directory = input()

            if not init_directory.strip():
                init_directory = os.path.join(animius_dir, 'resources')

            self.directories = {}

            # create sub directories
            for sub_dir in sub_dirs:
                sub_dir_path = os.path.join(init_directory, sub_dir)
                if not os.path.exists(sub_dir_path):
                    os.mkdir(sub_dir_path)
                self.directories[sub_dir] = sub_dir_path

        else:  # load config

            with open(self.config_dir, 'r') as f:
                stored = json.load(f)

            self.directories = stored['directories']

            # read all saved items
            for sub_dir in sub_dirs:
                with open(os.path.join(self.directories[sub_dir], sub_dir + '.json'), 'r'):
                    stored = json.load(f)
                for item in stored['items']:
                    console_item = _ConsoleItem()
                    console_item.saved_directory = stored['items'][item]['saved_directory']
                    console_item.saved_name = stored['items'][item]['saved_name']
                    # get the self. dictionary from sub_dir name
                    getattr(self, sub_dir)[item] = console_item

    def save(self):
        with open(self.config_dir, 'w') as f:
            json.dump({'directories': self.directories}, f, indent=4)

        # save all items
        for sub_dir in {'waifus', 'models', 'model_configs', 'data', 'embeddings'}:
            tmp_dict = {}
            for item_name, console_item in getattr(self, sub_dir).items():
                tmp_dict[item_name] = {'saved_directory': console_item.saved_directory,
                                       'saved_name': console_item.saved_name}
            with open(os.path.join(self.directories[sub_dir], sub_dir + '.json'), 'w') as f:
                json.dump({'items': tmp_dict}, f)

    @staticmethod
    def check_arguments(args, hard_requirements=None, soft_requirements=None):
        # Check if the user-provided arguments meet the requirements of the method/command
        # hard_requirement throws ArgumentError if not fulfilled
        # soft_requirement gives a value of None
        if hard_requirements is not None:
            for req in hard_requirements:
                if req not in args:
                    raise ArgumentError("{0} is required".format(req))

        if soft_requirements is not None:
            for req in soft_requirements:
                if req not in args:
                    args['req'] = None

    def create_model_config(self, **kwargs):
        """
        Create a model config with the provided values

        :param kwargs:

        :Keyword Arguments:
        * *name* (``str``) -- Name of model config
        * *cls* (``str``) -- Name of the model class
        * *config* (``dict``) -- Dictionary of config values
        * *hyperparameters* (``dict``) -- Dictionary of hyperparameters values
        * *model_structure* (``model_structure``) -- Dictionary of model_structure values
        """
        Console.check_arguments(kwargs,
                                hard_requirements=['name', 'cls'],
                                soft_requirements=['config', 'hyperparameters', 'model_structure'])

        if kwargs['name'] in self.model_configs:
            raise NameAlreadyExistError("The name {0} is already used by another model config".format(kwargs['name']))

        model_config = am.ModelConfig(kwargs['cls'],
                                      kwargs['config'],
                                      kwargs['hyperparameters'],
                                      kwargs['model_structure'])

        # saving it first to set up its saving location
        model_config.save(self.directories['model_configs'], kwargs['name'])

        console_item = _ConsoleItem(model_config)
        console_item.saved_directory = self.directories['model_configs']
        console_item.saved_name = kwargs['name']

        self.model_configs[kwargs['name']] = console_item

    def edit_model_config(self, **kwargs):
        """
        Update a model config with the provided values

        :param kwargs:

        :Keyword Arguments:
        * *name* (``str``) -- Name of model config to edit
        * *config* (``dict``) -- Dictionary containing the updated config values
        * *hyperparameters* (``dict``) -- Dictionary containing the updated hyperparameters values
        * *model_structure* (``model_structure``) -- Dictionary containing the updated model_structure values
        """
        Console.check_arguments(kwargs,
                                hard_requirements=['name'])

        if kwargs['name'] in self.model_configs:
            def update_dict(target, update_values):
                for key in update_values:
                    target[key] = update_values[key]

            update_dict(self.model_configs[kwargs['name']].item.config, kwargs['config'])
            update_dict(self.model_configs[kwargs['name']].item.hyperparameters, kwargs['hyperparameters'])
            update_dict(self.model_configs[kwargs['name']].item.model_structure, kwargs['model_structure'])

        else:
            raise KeyError("Model config \"{0}\" not found.".format(kwargs['name']))

    def delete_model_config(self, **kwargs):
        """
        Delete a model config

        :param kwargs:

        :Keyword Arguments:
        * *name* (``str``) -- Name of model config to delete
        """
        Console.check_arguments(kwargs,
                                hard_requirements=['name'])

        if kwargs['name'] in self.model_configs:
            self.model_configs.pop(kwargs['name'])
        else:
            raise KeyError("Model config \"{0}\" not found.".format(kwargs['name']))

    def create_data(self, **kwargs):
        """
        Create a data with empty values

        :param kwargs:

        :Keyword Arguments:
        * *name* (``str``) -- Name of data
        * *type* (``str``) -- Type of data (based on the model)
        * *model_config* (``str``) -- Name of model config
        """
        Console.check_arguments(kwargs,
                                hard_requirements=['name', 'type', 'model_config'])

        if kwargs['name'] in self.data:
            raise NameAlreadyExistError("The name {0} is already used by another data".format(kwargs['name']))

        if kwargs['model_config'] in self.model_configs:
            if kwargs['type'] == 'ChatbotData':
                data = am.ChatbotData(kwargs['model_config'])
            elif kwargs['type'] == 'IntentNERData':
                data = am.IntentNERData(kwargs['model_config'])
            elif kwargs['type'] == 'SpeakerVerificationData':
                data = am.SpeakerVerificationData(kwargs['model_config'])
            else:
                raise KeyError("Data type \"{0}\" not found.".format(kwargs['type']))
        else:
            raise KeyError("Model config \"{0}\" not found.".format(kwargs['name']))

        # saving it first to set up its saving location
        save_dir = os.path.join(self.directories['data'], kwargs['name'])
        data.save(save_dir, kwargs['name'])

        console_item = _ConsoleItem(data)
        console_item.saved_directory = save_dir
        console_item.saved_name = kwargs['name']

        self.data[kwargs['name']] = console_item

    def data_add_embedding(self, **kwargs):
        """
        Add twitter dataset to a chatbot data.

        :param kwargs:

        :Keyword Arguments:
        * *name* (``str``) -- Name of data to add on
        * *name_embedding* (``str``) -- Name of the embedding to add to data
        """
        Console.check_arguments(kwargs,
                                hard_requirements=['name', 'name_embedding'])

        if kwargs['name'] in self.data:
            if kwargs['name_embedding'] in self.embeddings:
                self.data[kwargs['name']].item.add_embedding_class(self.embeddings[kwargs['name_embedding']].item)
            else:
                raise KeyError("Embedding \"{0}\" not found.".format(kwargs['name_embedding']))
        else:
            raise KeyError("Data \"{0}\" not found.".format(kwargs['name']))

    def data_reset(self, **kwargs):
        """
        Reset a data, clearing all stored data values.

        :param kwargs:

        :Keyword Arguments:
        * *name* (``str``) -- Name of data to reset
        """
        Console.check_arguments(kwargs,
                                hard_requirements=['name'])

        if kwargs['name'] in self.data:
            self.data[kwargs['name']].item.reset()
        else:
            raise KeyError("Data \"{0}\" not found.".format(kwargs['name']))

    def chatbot_data_add_twitter(self, **kwargs):
        """
        Add twitter dataset to a chatbot data.

        :param kwargs:

        :Keyword Arguments:
        * *name* (``str``) -- Name of data to add on
        * *path* (``str``) -- Path to twitter file
        """
        Console.check_arguments(kwargs,
                                hard_requirements=['name', 'path'])

        if kwargs['name'] in self.data:
            if isinstance(self.data[kwargs['name']].item, am.ChatbotData):
                self.data[kwargs['name']].item.add_twitter(kwargs['path'])
            else:
                raise KeyError("Data \"{0}\" is not a ChatbotData.".format(kwargs['name']))
        else:
            raise KeyError("Data \"{0}\" not found.".format(kwargs['name']))

    def chatbot_data_add_cornell(self, **kwargs):
        """
        Add Cornell dataset to a chatbot data.

        :param kwargs:

        :Keyword Arguments:
        * *name* (``str``) -- Name of data to add on
        * *movie_conversations_path* (``str``) -- Path to movie_conversations.txt in the Cornell dataset
        * *movie_lines_path* (``str``) -- Path to movie_lines.txt in the Cornell dataset
        """
        Console.check_arguments(kwargs,
                                hard_requirements=['name', 'movie_conversations_path', 'movie_lines_path'])

        if kwargs['name'] in self.data:
            if isinstance(self.data[kwargs['name']].item, am.ChatbotData):
                self.data[kwargs['name']].item.add_cornell(kwargs['movie_conversations_path'], kwargs['movie_lines_path'])
            else:
                raise KeyError("Data \"{0}\" is not a ChatbotData.".format(kwargs['name']))
        else:
            raise KeyError("Data \"{0}\" not found.".format(kwargs['name']))

    def chatbot_data_add_parse_sentences(self, **kwargs):
        """
        Parse raw sentences and add them to a chatbot data.

        :param kwargs:

        :Keyword Arguments:
        * *name* (``str``) -- Name of data to add on
        * *x* (``list<str>``) -- List of strings, each representing a sentence input
        * *y* (``list<str>``) -- List of strings, each representing a sentence output
        """
        Console.check_arguments(kwargs,
                                hard_requirements=['name', 'x', 'y'])

        if kwargs['name'] in self.data:
            if isinstance(self.data[kwargs['name']].item, am.ChatbotData):
                self.data[kwargs['name']].item.add_parse_sentences(kwargs['x'], kwargs['y'])
            else:
                raise KeyError("Data \"{0}\" is not a ChatbotData.".format(kwargs['name']))
        else:
            raise KeyError("Data \"{0}\" not found.".format(kwargs['name']))

    def chatbot_data_add_parse_file(self, **kwargs):
        """
        Parse raw sentences from text files and add them to a chatbot data.

        :param kwargs:

        :Keyword Arguments:
        * *name* (``str``) -- Name of data to add on
        * *x_path* (``str``) -- Path to a UTF-8 file containing a raw sentence input on each line
        * *y_path* (``str``) -- Path to a UTF-8 file containing a raw sentence output on each line
        """
        Console.check_arguments(kwargs,
                                hard_requirements=['name', 'x_path', 'y_path'])

        if kwargs['name'] in self.data:
            if isinstance(self.data[kwargs['name']].item, am.ChatbotData):
                self.data[kwargs['name']].item.add_parse_file(kwargs['x_path'], kwargs['y_path'])
            else:
                raise KeyError("Data \"{0}\" is not a ChatbotData.".format(kwargs['name']))
        else:
            raise KeyError("Data \"{0}\" not found.".format(kwargs['name']))

    def chatbot_data_add_parse_input(self, **kwargs):
        """
        Parse a raw sentence as input and add it to a chatbot data.

        :param kwargs:

        :Keyword Arguments:
        * *name* (``str``) -- Name of data to add on
        * *x* (``str``) -- Raw sentence input
        """
        Console.check_arguments(kwargs,
                                hard_requirements=['name', 'x'])

        if kwargs['name'] in self.data:
            if isinstance(self.data[kwargs['name']].item, am.ChatbotData):
                self.data[kwargs['name']].item.add_parse_input(kwargs['x'])
            else:
                raise KeyError("Data \"{0}\" is not a ChatbotData.".format(kwargs['name']))
        else:
            raise KeyError("Data \"{0}\" not found.".format(kwargs['name']))

    def chatbot_data_set_parse_input(self, **kwargs):
        """
        Parse a raw sentence as input and set it as a chatbot data.

        :param kwargs:

        :Keyword Arguments:
        * *name* (``str``) -- Name of data to set
        * *x* (``str``) -- Raw sentence input
        """
        Console.check_arguments(kwargs,
                                hard_requirements=['name', 'x'])

        if kwargs['name'] in self.data:
            if isinstance(self.data[kwargs['name']].item, am.ChatbotData):
                self.data[kwargs['name']].item.set_parse_input(kwargs['x'])
            else:
                raise KeyError("Data \"{0}\" is not a ChatbotData.".format(kwargs['name']))
        else:
            raise KeyError("Data \"{0}\" not found.".format(kwargs['name']))

    def intentNER_data_add_parse_data_folder(self, **kwargs):
        """
        Parse files from a folder and add them to a chatbot data.

        :param kwargs:

        :Keyword Arguments:
        * *name* (``str``) -- Name of data to add on
        * *folder_directory* (``str``) -- Path to a folder contains input files
        """
        Console.check_arguments(kwargs,
                                hard_requirements=['name', 'folder_directory'])

        if kwargs['name'] in self.data:
            if isinstance(self.data[kwargs['name']].item, am.IntentNERData):
                self.data[kwargs['name']].item.add_parse_data_folder(kwargs['folder_directory'])
            else:
                raise KeyError("Data \"{0}\" is not a IntentNERData.".format(kwargs['name']))
        else:
            raise KeyError("Data \"{0}\" not found.".format(kwargs['name']))

    def intentNER_data_add_parse_input(self, **kwargs):
        """
        Parse a raw sentence as input and add it to an intent NER data.

        :param kwargs:

        :Keyword Arguments:
        * *name* (``str``) -- Name of data to add on
        * *x* (``str``) -- Raw sentence input
        """
        Console.check_arguments(kwargs,
                                hard_requirements=['name', 'x'])

        if kwargs['name'] in self.data:
            if isinstance(self.data[kwargs['name']].item, am.IntentNERData):
                self.data[kwargs['name']].item.add_parse_input(kwargs['x'])
            else:
                raise KeyError("Data \"{0}\" is not a IntentNERData.".format(kwargs['name']))
        else:
            raise KeyError("Data \"{0}\" not found.".format(kwargs['name']))

    def intentNER_data_set_parse_input(self, **kwargs):
        """
        Parse a raw sentence as input and set it as an intent NER data.

        :param kwargs:

        :Keyword Arguments:
        * *name* (``str``) -- Name of data to set
        * *x* (``str``) -- Raw sentence input
        """
        Console.check_arguments(kwargs,
                                hard_requirements=['name', 'x'])

        if kwargs['name'] in self.data:
            if isinstance(self.data[kwargs['name']].item, am.IntentNERData):
                self.data[kwargs['name']].item.set_parse_input(kwargs['x'])
            else:
                raise KeyError("Data \"{0}\" is not a IntentNERData.".format(kwargs['name']))
        else:
            raise KeyError("Data \"{0}\" not found.".format(kwargs['name']))

    def speakerVerification_data_add_data_paths(self, **kwargs):
        """
        Parse and add raw audio files to a speaker verification data

        :param kwargs:

        :Keyword Arguments:
        * *name* (``str``) -- Name of data to add on
        * *paths* (``list<str>``) -- List of string paths to raw audio files
        * *y* (``bool``) -- The label (True for is speaker and vice versa) of the audio files. Optional. Include for training, leave out for prediction.
        """
        Console.check_arguments(kwargs,
                                hard_requirements=['name', 'paths'],
                                soft_requirements=['y'])

        if kwargs['name'] in self.data:
            if isinstance(self.data[kwargs['name']].item, am.SpeakerVerificationData):
                self.data[kwargs['name']].item.add_parse_data_paths(kwargs['paths'],kwargs['y'])
            else:
                raise KeyError("Data \"{0}\" is not a SpeakerVerificationData.".format(kwargs['name']))
        else:
            raise KeyError("Data \"{0}\" not found.".format(kwargs['name']))

    def speakerVerification_data_add_data_file(self, **kwargs):
        """
        Read paths to raw audio files and add them to a speaker verification data

        :param kwargs:

        :Keyword Arguments:
        * *name* (``str``) -- Name of data to add on
        * *path* (``str``) -- Path to file containing a path of a raw audio file on each line
        * *y* (``bool``) -- The label (True for is speaker and vice versa) of the audio files. Optional. Include for training, leave out for prediction.
        """
        Console.check_arguments(kwargs,
                                hard_requirements=['name', 'paths'],
                                soft_requirements=['y'])

        if kwargs['name'] in self.data:
            if isinstance(self.data[kwargs['name']].item, am.SpeakerVerificationData):
                self.data[kwargs['name']].item.add_parse_data_file(kwargs['paths'], kwargs['y'])
            else:
                raise KeyError("Data \"{0}\" is not a SpeakerVerificationData.".format(kwargs['name']))
        else:
            raise KeyError("Data \"{0}\" not found.".format(kwargs['name']))

    def delete_data(self, **kwargs):
        """
        Delete a data

        :param kwargs:

        :Keyword Arguments:
        * *name* (``str``) -- Name of data to delete
        """
        Console.check_arguments(kwargs,
                                hard_requirements=['name'])

        if kwargs['name'] in self.data:
            self.data.pop(kwargs['name'])

        else:
            raise KeyError("Data \"{0}\" not found.".format(kwargs['name']))

    def create_embedding(self, **kwargs):
        """
        Create a word embedding

        :param kwargs:

        :Keyword Arguments:
        * *name* (``str``) -- Name of embedding
        * *path* (``str``) -- Path to embedding file
        * *vocab_size* (``int``) -- Maximum number of tokens to read from embedding file
        """
        Console.check_arguments(kwargs,
                                hard_requirements=['name', 'path'],
                                soft_requirements=['vocab_size'])

        embedding = am.WordEmbedding()
        if kwargs['vocab_size'] is not None:
            embedding.create_embedding(kwargs['path'], kwargs['vocab_size'])
        else:
            embedding.create_embedding(kwargs['path'])

        # saving it first to set up its saving location
        save_dir = os.path.join(self.directories['embeddings'], kwargs['name'])
        embedding.save(save_dir, kwargs['name'])

        console_item = _ConsoleItem(embedding)
        console_item.saved_directory = save_dir
        console_item.saved_name = kwargs['name']

        self.embeddings[kwargs['name']] = console_item

    def delete_embedding(self, **kwargs):
        """
        Delete a word embedding

        :param kwargs:

        :Keyword Arguments:
        * *name* (``str``) -- Name of embedding to delete
        """
        Console.check_arguments(kwargs,
                                hard_requirements=['name'])

        if kwargs['name'] in self.embeddings:
            self.embeddings.pop(kwargs['name'])

        else:
            raise KeyError("Embedding \"{0}\" not found.".format(kwargs['name']))

    def handle_network(self, request):

        command = request.command.lower().replace(' ', '_')
        method_to_call = getattr(self, command)

        try:
            result = method_to_call(request.arguments)
            if result is None:
                result = {}
            return request.id, 0, 'success', result
        except ArgumentError as exc:
            return request.id, 1, exc, {}
        except Exception as exc:
            return request.id, 2, exc, {}
