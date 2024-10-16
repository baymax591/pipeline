import copy
from functools import cached_property
from typing import Callable, Optional, List, Union

from loguru import logger

from ...base import BasePipelineWrapper, MSBasePipeline
from .ms_utils import pipeline_registry


class PipelineWrapper(BasePipelineWrapper):
  def __init__(self,
               task: str = None,
               default_framework: str = None,
               default_model: str = None,
               default_backend: str = None,
               **kwargs):
    super().__init__(task, default_framework, default_model, default_backend, **kwargs)


class MSPipeline(MSBasePipeline):
  def __init__(self,
               task: str = None, 
               model: str = None,
               tokenizer: str = None,
               image_processor: str = None,
               audio_processor: str = None,
               backend: str = None,
               **kwargs):
    self.task = task
    self.model = model
    self.tokenizer =tokenizer
    self.image_processor = image_processor
    self.audio_processor = audio_processor
    self.backend = backend
    self.kwargs = copy.deepcopy(kwargs)

    # access pipeline here to trigger download and load
    self.pipeline

  @cached_property
  def pipeline(self) -> Callable:
    try:
      pipeline_creator = pipeline_registry.get(self.task).get(self.framework).get(self.backend)
    except Exception as e:
      # If any error occurs, we issue a warning, but don't exit immediately.
      logger.warning(
        "An error occurred while trying to get pipline creator. Error"
        f" details: {e}"
      )
      pipeline_creator = None
    if pipeline_creator is None:
      raise ValueError(f"Could not find pipeline creator for {self.task}:{self.framework}:{self.backend}")
    
    logger.info(
      f"Creating pipeline for {self.task}(framework={self.framework}, backend={self.backend},"
      f" model={self.model}, revision={self.revision}).\n"
      "openMind download might take a while, please be patient..."
    )

    try:
      # TODO: 确认这里要传入什么参数
      pipeline = pipeline_creator(
        task=self.task,
        model=self.model,
        tokenizer=self.tokenizer,
        image_processor=self.image_processor,
        audio_processor=self.audio_processor,
        **self.kwargs,
      )
    except ImportError as e:
      # TODO: add more user-friendly error messages
      raise e
    return pipeline

  def _run_pipeline(self, *args, **kwargs):
    # TODO: do we need this?
    try:
      import torch
      # from accelerate import
      from accelerate.utils import is_npu_available
      if is_npu_available():
        import torch_npu
    except ImportError as e:
      # TODO: add more user-friendly error messages
      raise e

    return self.pipeline(*args, **kwargs)


def _get_generated_text(res):
    if isinstance(res, str):
        return res
    elif isinstance(res, dict):
        return res["generated_text"]
    elif isinstance(res, list):
        if len(res) == 1:
            return _get_generated_text(res[0])
        else:
            return [_get_generated_text(r) for r in res]
    else:
        raise ValueError(f"Unsupported result type in _get_generated_text: {type(res)}")


class TextGenerationPipeline(MSPipeline):
  def __init__(self,
               task: str = None, 
               model: str = None,
               tokenizer: str = None,
               image_processor: str = None,
               audio_processor: str = None,
               backend: str = None,
               **kwargs):
    self.task = task
    self.model = model
    self.tokenizer = tokenizer
    self.image_processor = image_processor
    self.audio_processor = audio_processor
    self.framework = "ms"
    self.backend = "mindformers"
    self.kwargs = copy.deepcopy(kwargs)

    # access pipeline here to trigger download and load
    self.pipeline
  
  def __call__(
    self,
    inputs: Union[str, List[str]],
    top_k: Optional[int] = None,
    top_p: Optional[float] = None,
    temperature: Optional[float] = 1.0,
    repetition_penalty: Optional[float] = None,
    max_new_tokens: Optional[int] = None,
    max_time: Optional[float] = None,
    return_full_text: bool = True,
    num_return_sequences: int = 1,
    do_sample: bool = True,
    **kwargs,
  ) -> Union[str, List[str]]:
    res = self._run_pipeline(
      inputs,
      top_k=top_k,
      top_p=top_p,
      temperature=temperature,
      repetition_penalty=repetition_penalty,
      max_new_tokens=max_new_tokens,
      max_time=max_time,
      return_full_text=return_full_text,
      num_return_sequences=num_return_sequences,
      do_sample=do_sample,
      **kwargs,
    )

    return _get_generated_text(res)
