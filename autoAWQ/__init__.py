######
# Project       : lollms
# File          : binding.py
# Author        : ParisNeo with the help from bartowski
# Underlying 
# engine author : turboderp 
# license       : Apache 2.0
# Description   : 
# This is an interface class for lollms bindings.
# Big thank you to turboderp and oobabooga for their
# paving the way with their work
######
from pathlib import Path
from typing import Callable
from lollms.config import BaseConfig, TypedConfig, ConfigTemplate, InstallOption
from lollms.paths import LollmsPaths
from lollms.binding import LLMBinding, LOLLMSConfig
from lollms.helpers import ASCIIColors
from lollms.types import MSG_TYPE
from lollms.helpers import trace_exception
from lollms.utilities import AdvancedGarbageCollector
import subprocess
import yaml
import re
import urllib
import shutil
import sys
import os
import platform

# sys.path.append(os.getcwd())
# pth = Path(__file__).parent/"exllamav2"
# sys.path.append(str(pth))


__author__ = "parisneo"
__github__ = "https://github.com/ParisNeo/lollms_bindings_zoo"
__copyright__ = "Copyright 2023, "
__license__ = "Apache 2.0"

binding_name = "AutoAWQ"
binding_folder_name = "autoAWQ"
import os
import subprocess
import torch
class AutoAWQ(LLMBinding):
    
    def __init__(self, 
                config: LOLLMSConfig, 
                lollms_paths: LollmsPaths = None, 
                installation_option:InstallOption=InstallOption.INSTALL_IF_NECESSARY
                ) -> None:
        """Builds an Exllama binding

        Args:
            config (LOLLMSConfig): The configuration file
        """
        self.model          = None
        self.tokenizer      = None
        self.cache          = None
        self.generator      = None
                
        if lollms_paths is None:
            lollms_paths = LollmsPaths()

        # Initialization code goes here
        binding_config_template = ConfigTemplate([
            
            {"name": "gpu_split", "type": "str", "value": '[24]',
                "help": "A list depicting how many layers to offload to each GPU. [gpu1,gpu2 etc]. Example [16,24]. If you have just one, the list should contain one value"},
            {"name": "ctx_size", "type": "int", "value": 2048, "min": 512,
                "help": "The current context size (it depends on the model you are using). Make sure the context size if correct or you may encounter bad outputs. Reduce to save memory. Can also be increased, ideally while also using compress_pos_emn and a compatible model/LoRA"},
            {"name": "max_input_len", "type": "int", "value": 2048, "min": 512,
                "help": "Maximum length of input IDs in a single forward pass. Sequences longer than this will be processed in multiple steps"},
            {"name": "max_attention_size", "type": "int", "value": 2048**2, "min": 512,
                "help": "Increase to compress positional embeddings applied to sequence"},
            {"name": "compress_pos_emb", "type": "float", "value": 1, "min": 1, "max": 8,
                "help": "Positional embeddings compression value, set it to your ctx_size divided by 2048 when over 2048. Only set this or alpha. Increase to compress positional embeddings applied to sequence"},
            {"name": "alpha", "type": "int", "value": 1, "min": 1, "max": 32,
                "help": "Alpha value for context size extension. Only use this or compress_pos_emb. Alpha value for NTK RoPE scaling. Similar to compress_pos_emb, higher values increaste ctx but add Perplexity."},
        ])
        binding_config_vals = BaseConfig.from_template(binding_config_template)

        binding_config = TypedConfig(
            binding_config_template,
            binding_config_vals
        )
        super().__init__(
                            Path(__file__).parent, 
                            lollms_paths, 
                            config, 
                            binding_config, 
                            installation_option,
                            supported_file_extensions=['.safetensors','.pth','.bin']
                        )

        
        self.config.ctx_size = self.binding_config.config.ctx_size
        self.callback = None
        self.n_generated = 0
        self.n_prompt = 0

        self.skip_prompt = True
        self.decode_kwargs = {}

        # variables used in the streaming process
        self.token_cache = []
        self.print_len = 0
        self.next_tokens_are_prompt = True

    def build_model(self):

        try:
            from awq import AutoAWQForCausalLM
            from transformers import AutoTokenizer, TextStreamer
        except Exception as ex:
            trace_exception(ex)
            ASCIIColors.warning("Couldn't import dependencies? REINSTALL BINDING")
            return

        if self.config.model_name is None:
            ASCIIColors.error('No model selected!!')
            return

        if self.config.model_name:

            path = self.config.model_name
            model_path = self.get_model_path()

            if not model_path:
                self.model = None
                return None

            models_dir = self.lollms_paths.personal_models_path / "awq"
            models_dir.mkdir(parents=True, exist_ok=True)

            # model_path = models_dir/ path

            model_name = str(model_path).replace("\\","/")

            for ext in ['.safetensors', '.pt', '.bin']:
                found = list(model_path.glob(f"*{ext}"))
                if len(found) > 0:
                    if len(found) > 1:
                        print(
                            f'More than one {ext} model has been found. The last one will be selected. It could be wrong.')

                    model_file = found[-1]
                    break        

            self.clear_cuda()
            ASCIIColors.red ("----------- LOLLMS AutoAWQ Model Information -----------------")
            ASCIIColors.magenta(f"Model name:{self.config.model_name}")
            self.print_class_attributes(config)
            ASCIIColors.red ("--------------------------------------------------------------")
            self.model = AutoAWQForCausalLM.from_quantized(model_path, model_file, fuse_layers=True)
            self.tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
            self.streamer = self#TextStreamer(tokenizer, skip_special_tokens=True)


            return self

    def __del__(self):
        del self.generator
        del self.cache
        del self.tokenizer
        del self.model
        try:
            torch.cuda.empty_cache()
        except Exception as ex:
            ASCIIColors.error("Couldn't clear cuda memory")

    def install(self):
        # free up memory
        ASCIIColors.success("freeing memory")
        AdvancedGarbageCollector.safeHardCollectMultiple(['model','tokenizer','cache','generator'],self)
        AdvancedGarbageCollector.safeHardCollectMultiple(['ExLlamaGenerator','ExLlama','ExLlamaCache','ExLlamaConfig','ExLlamaTokenizer','torch_version'])
        AdvancedGarbageCollector.collect()
        self.clear_cuda()
        ASCIIColors.success("freed memory")
        
        super().install()
        print("This is the first time you are using this binding.")
                # Step 1 : install pytorch with cuda
        ASCIIColors.info("Checking pytorch")
        
        if self.config.enable_gpu:
            try:
                import torch
                from torch import version as torch_version
                try:
                    torch.cuda.empty_cache()
                except Exception as ex:
                    ASCIIColors.error("Couldn't clear cuda memory")
            except:
                pass       
            try:
                if torch.cuda.is_available():
                    ASCIIColors.success("CUDA is supported.")
                else:
                    ASCIIColors.warning("CUDA is not supported. Trying to reinstall PyTorch with CUDA support.")
                    self.reinstall_pytorch_with_cuda()
            except Exception as ex:
                ASCIIColors.info("Pytorch not installed")
                self.reinstall_pytorch_with_cuda()


            models_dir = self.lollms_paths.personal_models_path / "awq"
            models_dir.mkdir(parents=True, exist_ok=True)

            subprocess.run(["pip", "install", "--upgrade", "autoawq"])
        else:
            ASCIIColors.error("autoawq is only installable on GPU. Please activate GPU support before proceeding")
            


    def uninstall(self):
        super().install()
        print("Uninstalling binding.")
        subprocess.run(["pip", "uninstall", "--yes", "llama-cpp-python"])
        ASCIIColors.success("Installed successfully")



    def tokenize(self, prompt:str):
        """
        Tokenizes the given prompt using the model's tokenizer.

        Args:
            prompt (str): The input prompt to be tokenized.

        Returns:
            list: A list of tokens representing the tokenized prompt.
        """
        t = self.tokenizer.encode(prompt)
        return t[0].tolist()

    def detokenize(self, tokens_list:list):
        """
        Detokenizes the given list of tokens using the model's tokenizer.

        Args:
            tokens_list (list): A list of tokens to be detokenized.

        Returns:
            str: The detokenized text as a string.
        """
        t = torch.IntTensor([tokens_list])
        return  self.tokenizer.decode(t)[0]
    


    def generate(self, 
                 prompt:str,                  
                 n_predict: int = 128,
                 callback: Callable[[str], None] = bool,
                 verbose: bool = False,
                 **gpt_params ):
        """Generates text out of a prompt

        Args:
            prompt (str): The prompt to use for generation
            n_predict (int, optional): Number of tokens to prodict. Defaults to 128.
            callback (Callable[[str], None], optional): A callback function that is called everytime a new text element is generated. Defaults to None.
            verbose (bool, optional): If true, the code will spit many informations about the generation process. Defaults to False.
        """
        self.callback = callback
        default_params = {
            'temperature': 0.7,
            'top_k': 50,
            'top_p': 0.96,
            'repeat_penalty': 1.3,
            "seed":-1,
            "n_threads":8,
            "typical_p":0.0
        }
        self.output = ""
        try:
            input_ids = self.tokenizer(
                prompt_template.format(prompt="How are you today?"), 
                return_tensors='pt'
            ).input_ids.cuda()
            prompt_tokens = input_ids.shape[-1]
            self.generator.warmup()
        except Exception as ex:
            ASCIIColors.error(ex)
            trace_exception(ex)
            if callback:
                callback(str(ex),MSG_TYPE.MSG_TYPE_EXCEPTION)
        return self.output

    @staticmethod
    def get_filenames(repo):
        import requests
        from bs4 import BeautifulSoup

        dont_download = [".gitattributes"]

        main_url = '/'.join(repo.split("/")[:-3])+"/tree/main" #f"https://huggingface.co/{}/tree/main"
        response = requests.get(main_url)
        html_content = response.text
        soup = BeautifulSoup(html_content, 'html.parser')

        file_names = []

        for a_tag in soup.find_all('a', {'class': 'group'}):
            span_tag = a_tag.find('span', {'class': 'truncate'})
            if span_tag:
                file_name = span_tag.text
                if file_name not in dont_download:
                    file_names.append(file_name)

        print(f"Repo: {repo}")
        print("Found files:")
        for file in file_names:
            print(" ", file)
        return file_names
                    
    @staticmethod
    def download_model(repo, base_folder, callback=None):
        """
        Downloads a folder from a Hugging Face repository URL, reports the download progress using a callback function,
        and displays a progress bar.

        Args:
            repo (str): The name of the Hugging Face repository.
            base_folder (str): The base folder where the repository should be saved.
            installation_path (str): The path where the folder should be saved.
            callback (function, optional): A callback function to be called during the download
                with the progress percentage as an argument. Defaults to None.
        """
        
        import wget
        import os
        from tqdm import tqdm

        file_names = AutoAWQ.get_filenames(repo)

        dest_dir = Path(base_folder)
        dest_dir.mkdir(parents=True, exist_ok=True)
        os.chdir(dest_dir)

        loading = ["none"]
        previous = [0]
        pbar = tqdm(total=100, desc="Processing", unit="step")
        def chunk_callback(current, total, width=80):
            # This function is called for each received chunk
            # Perform actions or computations on the received chunk
            # chunk: The chunk of data received
            # chunk_size: The size of each chunk in bytes
            # total_size: The total size of the file being downloaded

            # Example: Print the current progress
            downloaded = current 
            progress = (current  / total) * 100
            pbar.update(current-previous[0])  # Update the tqdm progress bar
            previous[0] = current
            if callback and ".safetensors" in loading[0]:
                try:
                    callback(downloaded, total)
                except:
                    callback(0, downloaded, total)
                    
        def download_file(get_file):
            src = "/".join(repo.split("/")[:-3])
            filename = f"{src}/resolve/main/{get_file}"
            print(f"\nDownloading {filename}")
            loading[0]=filename
            wget.download(filename, out=str(dest_dir), bar=chunk_callback)

        # with concurrent.futures.ThreadPoolExecutor() as executor:
        #     executor.map(download_file, file_names)
        for file_name in file_names:
            download_file(file_name)

        print("Done")
        
    def get_file_size(self, url):
        file_names = AutoAWQ.get_filenames(url)
        for file_name in file_names:
            if file_name.endswith(".safetensors"):
                src = "/".join(url.split("/")[:-3])
                filename = f"{src}/resolve/main/{file_name}"                
                response = urllib.request.urlopen(filename)
                
                # Extract the Content-Length header value
                file_size = response.headers.get('Content-Length')
                
                # Convert the file size to integer
                if file_size:
                    file_size = int(file_size)
                
                return file_size        
        return 4000000000

    def list_models(self, config:dict):
        """Lists the models for this binding
        """
        models_dir:Path = self.lollms_paths.personal_models_path/config["binding_name"]  # replace with the actual path to the models folder
        return [f.name for f in models_dir.iterdir() if f.is_dir() and not f.stem.startswith(".") or f.suffix==".reference"]

    @staticmethod
    def get_available_models():
        # Create the file path relative to the child class's directory
        binding_path = Path(__file__).parent
        file_path = binding_path/"models.yaml"

        with open(file_path, 'r') as file:
            yaml_data = yaml.safe_load(file)
        
        return yaml_data