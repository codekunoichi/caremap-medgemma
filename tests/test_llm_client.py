"""
Tests for caremap.llm_client module.
"""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock, PropertyMock
import torch

from caremap.llm_client import (
    pick_device,
    pick_dtype,
    GenerationConfig,
    MedGemmaClient,
)


class TestPickDevice:
    """Tests for pick_device function."""

    def test_returns_torch_device(self):
        device = pick_device()
        # Check it has the expected attributes of a torch.device
        assert hasattr(device, 'type')
        assert device.type in ("cpu", "cuda", "mps")

    @patch("torch.cuda.is_available", return_value=True)
    def test_prefers_cuda_when_available(self, mock_cuda):
        device = pick_device()
        assert device.type == "cuda"

    @patch("torch.cuda.is_available", return_value=False)
    def test_falls_back_to_cpu_when_no_gpu(self, mock_cuda):
        # Mock MPS as unavailable too by patching getattr behavior
        with patch("caremap.llm_client.torch") as mock_torch:
            mock_torch.cuda.is_available.return_value = False
            mock_torch.backends.mps = None
            mock_torch.device.side_effect = lambda x: torch.device(x)

            # Re-import to get fresh function with mocked torch
            from caremap.llm_client import pick_device as pick_device_fresh
            device = pick_device_fresh()
            assert device.type == "cpu"

    @patch("torch.cuda.is_available", return_value=True)
    def test_respects_cuda_preference(self, mock_cuda):
        device = pick_device(prefer="cuda")
        assert device.type == "cuda"

    def test_preference_ignored_if_unavailable(self):
        # Test that invalid preference falls back to available device
        device = pick_device(prefer="nonexistent")
        assert device.type in ("cpu", "cuda", "mps")

    def test_handles_empty_preference(self):
        device = pick_device(prefer="")
        assert hasattr(device, 'type')
        assert device.type in ("cpu", "cuda", "mps")

    def test_handles_whitespace_preference(self):
        device = pick_device(prefer="   ")
        assert hasattr(device, 'type')
        assert device.type in ("cpu", "cuda", "mps")

    def test_mps_preference_on_mac(self):
        """Test MPS preference when available."""
        device = pick_device(prefer="mps")
        # On Mac with MPS, should return MPS; otherwise CPU/CUDA
        assert device.type in ("cpu", "cuda", "mps")


class TestPickDtype:
    """Tests for pick_dtype function."""

    def test_returns_float32_for_cpu(self):
        device = torch.device("cpu")
        dtype = pick_dtype(device)
        assert dtype == torch.float32

    def test_returns_float16_for_cuda(self):
        device = torch.device("cuda")
        dtype = pick_dtype(device)
        assert dtype == torch.float16

    def test_returns_float16_for_mps(self):
        device = torch.device("mps")
        dtype = pick_dtype(device)
        assert dtype == torch.float16


class TestGenerationConfig:
    """Tests for GenerationConfig dataclass."""

    def test_default_values(self):
        config = GenerationConfig()
        assert config.max_new_tokens == 220
        assert config.do_sample is False
        assert config.temperature == 0.0
        assert config.top_p == 1.0

    def test_custom_values(self):
        config = GenerationConfig(
            max_new_tokens=100,
            do_sample=True,
            temperature=0.7,
            top_p=0.9
        )
        assert config.max_new_tokens == 100
        assert config.do_sample is True
        assert config.temperature == 0.7
        assert config.top_p == 0.9


class TestMedGemmaClient:
    """Tests for MedGemmaClient class."""

    @patch("caremap.llm_client.AutoTokenizer")
    @patch("caremap.llm_client.AutoModelForCausalLM")
    @patch("caremap.llm_client.pick_device")
    @patch("caremap.llm_client.pick_dtype")
    def test_initialization(self, mock_pick_dtype, mock_pick_device, mock_model_cls, mock_tokenizer_cls):
        """Test client initialization with mocked transformers."""
        mock_pick_device.return_value = torch.device("cpu")
        mock_pick_dtype.return_value = torch.float32

        mock_tokenizer = MagicMock()
        mock_tokenizer.pad_token_id = None
        mock_tokenizer.eos_token_id = 1
        mock_tokenizer_cls.from_pretrained.return_value = mock_tokenizer

        mock_model = MagicMock()
        mock_model.to.return_value = mock_model
        mock_model_cls.from_pretrained.return_value = mock_model

        client = MedGemmaClient(model_id="test/model", device="cpu")

        assert client.model_id == "test/model"
        assert client.device.type == "cpu"
        mock_tokenizer_cls.from_pretrained.assert_called_once()
        mock_model_cls.from_pretrained.assert_called_once()

    @patch("caremap.llm_client.AutoTokenizer")
    @patch("caremap.llm_client.AutoModelForCausalLM")
    @patch("caremap.llm_client.pick_device")
    @patch("caremap.llm_client.pick_dtype")
    def test_sets_pad_token_from_eos(self, mock_pick_dtype, mock_pick_device, mock_model_cls, mock_tokenizer_cls):
        """Test that pad_token_id is set from eos_token_id if not defined."""
        mock_pick_device.return_value = torch.device("cpu")
        mock_pick_dtype.return_value = torch.float32

        mock_tokenizer = MagicMock()
        mock_tokenizer.pad_token_id = None
        mock_tokenizer.eos_token_id = 50256
        mock_tokenizer_cls.from_pretrained.return_value = mock_tokenizer

        mock_model = MagicMock()
        mock_model.to.return_value = mock_model
        mock_model_cls.from_pretrained.return_value = mock_model

        client = MedGemmaClient(model_id="test/model", device="cpu")

        assert mock_tokenizer.pad_token_id == 50256

    @patch("caremap.llm_client.AutoTokenizer")
    @patch("caremap.llm_client.AutoModelForCausalLM")
    @patch("caremap.llm_client.pick_device")
    @patch("caremap.llm_client.pick_dtype")
    def test_generate_strips_prompt_echo(self, mock_pick_dtype, mock_pick_device, mock_model_cls, mock_tokenizer_cls):
        """Test that generate strips echoed prompt from output."""
        mock_pick_device.return_value = torch.device("cpu")
        mock_pick_dtype.return_value = torch.float32

        mock_tokenizer = MagicMock()
        mock_tokenizer.pad_token_id = 1
        mock_tokenizer.eos_token_id = 1
        mock_tokenizer.return_tensors = "pt"
        mock_tokenizer.return_value = {"input_ids": torch.tensor([[1, 2, 3]])}
        mock_tokenizer.decode.return_value = "Test prompt Response text"
        mock_tokenizer_cls.from_pretrained.return_value = mock_tokenizer

        mock_model = MagicMock()
        mock_model.to.return_value = mock_model
        mock_model.generate.return_value = torch.tensor([[1, 2, 3, 4, 5]])
        mock_model_cls.from_pretrained.return_value = mock_model

        client = MedGemmaClient(model_id="test/model", device="cpu")
        result = client.generate("Test prompt ")

        assert result == "Response text"

    @patch("caremap.llm_client.AutoTokenizer")
    @patch("caremap.llm_client.AutoModelForCausalLM")
    @patch("caremap.llm_client.pick_device")
    @patch("caremap.llm_client.pick_dtype")
    def test_generate_returns_full_output_when_no_echo(self, mock_pick_dtype, mock_pick_device, mock_model_cls, mock_tokenizer_cls):
        """Test that generate returns full output when prompt not echoed."""
        mock_pick_device.return_value = torch.device("cpu")
        mock_pick_dtype.return_value = torch.float32

        mock_tokenizer = MagicMock()
        mock_tokenizer.pad_token_id = 1
        mock_tokenizer.eos_token_id = 1
        mock_tokenizer.return_value = {"input_ids": torch.tensor([[1, 2, 3]])}
        mock_tokenizer.decode.return_value = "Different response"
        mock_tokenizer_cls.from_pretrained.return_value = mock_tokenizer

        mock_model = MagicMock()
        mock_model.to.return_value = mock_model
        mock_model.generate.return_value = torch.tensor([[1, 2, 3, 4, 5]])
        mock_model_cls.from_pretrained.return_value = mock_model

        client = MedGemmaClient(model_id="test/model", device="cpu")
        result = client.generate("Original prompt")

        assert result == "Different response"

    @patch("caremap.llm_client.AutoTokenizer")
    @patch("caremap.llm_client.AutoModelForCausalLM")
    @patch("caremap.llm_client.pick_device")
    @patch("caremap.llm_client.pick_dtype")
    def test_uses_custom_generation_config(self, mock_pick_dtype, mock_pick_device, mock_model_cls, mock_tokenizer_cls):
        """Test that custom GenerationConfig is used."""
        mock_pick_device.return_value = torch.device("cpu")
        mock_pick_dtype.return_value = torch.float32

        mock_tokenizer = MagicMock()
        mock_tokenizer.pad_token_id = 1
        mock_tokenizer.eos_token_id = 1
        mock_tokenizer_cls.from_pretrained.return_value = mock_tokenizer

        mock_model = MagicMock()
        mock_model.to.return_value = mock_model
        mock_model_cls.from_pretrained.return_value = mock_model

        custom_config = GenerationConfig(max_new_tokens=100, temperature=0.5)
        client = MedGemmaClient(
            model_id="test/model",
            device="cpu",
            gen_cfg=custom_config
        )

        assert client.gen_cfg.max_new_tokens == 100
        assert client.gen_cfg.temperature == 0.5

    @patch("caremap.llm_client.AutoTokenizer")
    @patch("caremap.llm_client.AutoModelForCausalLM")
    @patch("caremap.llm_client.pick_device")
    @patch("caremap.llm_client.pick_dtype")
    def test_model_set_to_eval_mode(self, mock_pick_dtype, mock_pick_device, mock_model_cls, mock_tokenizer_cls):
        """Test that model is set to eval mode after loading."""
        mock_pick_device.return_value = torch.device("cpu")
        mock_pick_dtype.return_value = torch.float32

        mock_tokenizer = MagicMock()
        mock_tokenizer.pad_token_id = 1
        mock_tokenizer_cls.from_pretrained.return_value = mock_tokenizer

        mock_model = MagicMock()
        mock_model.to.return_value = mock_model
        mock_model_cls.from_pretrained.return_value = mock_model

        client = MedGemmaClient(model_id="test/model", device="cpu")

        mock_model.eval.assert_called_once()

    @patch("caremap.llm_client.AutoTokenizer")
    @patch("caremap.llm_client.AutoModelForCausalLM")
    @patch("caremap.llm_client.pick_device")
    @patch("caremap.llm_client.pick_dtype")
    def test_multimodal_disabled_by_default(self, mock_pick_dtype, mock_pick_device, mock_model_cls, mock_tokenizer_cls):
        """Test that multimodal is disabled by default."""
        mock_pick_device.return_value = torch.device("cpu")
        mock_pick_dtype.return_value = torch.float32

        mock_tokenizer = MagicMock()
        mock_tokenizer.pad_token_id = 1
        mock_tokenizer_cls.from_pretrained.return_value = mock_tokenizer

        mock_model = MagicMock()
        mock_model.to.return_value = mock_model
        mock_model_cls.from_pretrained.return_value = mock_model

        client = MedGemmaClient(model_id="test/model", device="cpu")

        assert client.supports_multimodal is False

    @patch("caremap.llm_client.AutoTokenizer")
    @patch("caremap.llm_client.AutoModelForCausalLM")
    @patch("caremap.llm_client.pick_device")
    @patch("caremap.llm_client.pick_dtype")
    def test_generate_with_images_raises_when_disabled(self, mock_pick_dtype, mock_pick_device, mock_model_cls, mock_tokenizer_cls):
        """Test that generate_with_images raises when multimodal disabled."""
        mock_pick_device.return_value = torch.device("cpu")
        mock_pick_dtype.return_value = torch.float32

        mock_tokenizer = MagicMock()
        mock_tokenizer.pad_token_id = 1
        mock_tokenizer_cls.from_pretrained.return_value = mock_tokenizer

        mock_model = MagicMock()
        mock_model.to.return_value = mock_model
        mock_model_cls.from_pretrained.return_value = mock_model

        client = MedGemmaClient(model_id="test/model", device="cpu")

        with pytest.raises(RuntimeError, match="Multimodal mode not enabled"):
            client.generate_with_images("Test prompt", ["image.png"])


class TestGenerateWithImages:
    """Tests for generate_with_images method."""

    @patch("caremap.llm_client.Image")
    @patch("caremap.llm_client.hf_pipeline")
    @patch("caremap.llm_client.PIPELINE_AVAILABLE", True)
    @patch("caremap.llm_client.PIL_AVAILABLE", True)
    @patch("caremap.llm_client.AutoTokenizer")
    @patch("caremap.llm_client.AutoModelForCausalLM")
    @patch("caremap.llm_client.pick_device")
    @patch("caremap.llm_client.pick_dtype")
    def test_loads_image_from_file_path(self, mock_pick_dtype, mock_pick_device, mock_model_cls, mock_tokenizer_cls, mock_pipeline, mock_image):
        """Test that images are loaded from file paths."""
        import tempfile
        from pathlib import Path

        mock_pick_device.return_value = torch.device("cpu")
        mock_pick_dtype.return_value = torch.float32

        mock_tokenizer = MagicMock()
        mock_tokenizer.pad_token_id = 1
        mock_tokenizer_cls.from_pretrained.return_value = mock_tokenizer

        mock_model = MagicMock()
        mock_model.to.return_value = mock_model
        mock_model_cls.from_pretrained.return_value = mock_model

        mock_pipe = MagicMock()
        mock_pipe.return_value = [{"generated_text": [{"content": "Response"}]}]
        mock_pipeline.return_value = mock_pipe

        mock_pil_image = MagicMock()
        mock_image.open.return_value = mock_pil_image

        client = MedGemmaClient(model_id="test/model", device="cpu", enable_multimodal=True)

        # Create a temp file to simulate an image
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            temp_path = f.name

        try:
            result = client.generate_with_images("What is in this image?", [temp_path])
            assert result == "Response"
            mock_image.open.assert_called_once()
        finally:
            Path(temp_path).unlink()

    @patch("caremap.llm_client.Image")
    @patch("caremap.llm_client.hf_pipeline")
    @patch("caremap.llm_client.PIPELINE_AVAILABLE", True)
    @patch("caremap.llm_client.PIL_AVAILABLE", True)
    @patch("caremap.llm_client.AutoTokenizer")
    @patch("caremap.llm_client.AutoModelForCausalLM")
    @patch("caremap.llm_client.pick_device")
    @patch("caremap.llm_client.pick_dtype")
    def test_handles_url_images(self, mock_pick_dtype, mock_pick_device, mock_model_cls, mock_tokenizer_cls, mock_pipeline, mock_image):
        """Test that URL images are passed through to pipeline."""
        mock_pick_device.return_value = torch.device("cpu")
        mock_pick_dtype.return_value = torch.float32

        mock_tokenizer = MagicMock()
        mock_tokenizer.pad_token_id = 1
        mock_tokenizer_cls.from_pretrained.return_value = mock_tokenizer

        mock_model = MagicMock()
        mock_model.to.return_value = mock_model
        mock_model_cls.from_pretrained.return_value = mock_model

        mock_pipe = MagicMock()
        mock_pipe.return_value = [{"generated_text": [{"content": "URL Response"}]}]
        mock_pipeline.return_value = mock_pipe

        client = MedGemmaClient(model_id="test/model", device="cpu", enable_multimodal=True)

        result = client.generate_with_images("Describe this", ["https://example.com/image.png"])
        assert result == "URL Response"
        # Image.open should NOT be called for URLs
        mock_image.open.assert_not_called()

    @patch("caremap.llm_client.Image")
    @patch("caremap.llm_client.hf_pipeline")
    @patch("caremap.llm_client.PIPELINE_AVAILABLE", True)
    @patch("caremap.llm_client.PIL_AVAILABLE", True)
    @patch("caremap.llm_client.AutoTokenizer")
    @patch("caremap.llm_client.AutoModelForCausalLM")
    @patch("caremap.llm_client.pick_device")
    @patch("caremap.llm_client.pick_dtype")
    def test_handles_pil_image_directly(self, mock_pick_dtype, mock_pick_device, mock_model_cls, mock_tokenizer_cls, mock_pipeline, mock_image):
        """Test that PIL Image objects are passed through directly."""
        mock_pick_device.return_value = torch.device("cpu")
        mock_pick_dtype.return_value = torch.float32

        mock_tokenizer = MagicMock()
        mock_tokenizer.pad_token_id = 1
        mock_tokenizer_cls.from_pretrained.return_value = mock_tokenizer

        mock_model = MagicMock()
        mock_model.to.return_value = mock_model
        mock_model_cls.from_pretrained.return_value = mock_model

        mock_pipe = MagicMock()
        mock_pipe.return_value = [{"generated_text": [{"content": "PIL Response"}]}]
        mock_pipeline.return_value = mock_pipe

        client = MedGemmaClient(model_id="test/model", device="cpu", enable_multimodal=True)

        # Pass a mock PIL Image directly
        mock_pil_img = MagicMock()
        result = client.generate_with_images("What is this?", [mock_pil_img])
        assert result == "PIL Response"
        # Image.open should NOT be called when PIL image is passed directly
        mock_image.open.assert_not_called()

    @patch("caremap.llm_client.Image")
    @patch("caremap.llm_client.hf_pipeline")
    @patch("caremap.llm_client.PIPELINE_AVAILABLE", True)
    @patch("caremap.llm_client.PIL_AVAILABLE", True)
    @patch("caremap.llm_client.AutoTokenizer")
    @patch("caremap.llm_client.AutoModelForCausalLM")
    @patch("caremap.llm_client.pick_device")
    @patch("caremap.llm_client.pick_dtype")
    def test_raises_file_not_found_for_missing_image(self, mock_pick_dtype, mock_pick_device, mock_model_cls, mock_tokenizer_cls, mock_pipeline, mock_image):
        """Test that FileNotFoundError is raised for non-existent local files."""
        mock_pick_device.return_value = torch.device("cpu")
        mock_pick_dtype.return_value = torch.float32

        mock_tokenizer = MagicMock()
        mock_tokenizer.pad_token_id = 1
        mock_tokenizer_cls.from_pretrained.return_value = mock_tokenizer

        mock_model = MagicMock()
        mock_model.to.return_value = mock_model
        mock_model_cls.from_pretrained.return_value = mock_model

        mock_pipeline.return_value = MagicMock()

        client = MedGemmaClient(model_id="test/model", device="cpu", enable_multimodal=True)

        with pytest.raises(FileNotFoundError, match="Image not found"):
            client.generate_with_images("What is this?", ["/nonexistent/path/image.png"])

    @patch("caremap.llm_client.Image")
    @patch("caremap.llm_client.hf_pipeline")
    @patch("caremap.llm_client.PIPELINE_AVAILABLE", True)
    @patch("caremap.llm_client.PIL_AVAILABLE", True)
    @patch("caremap.llm_client.AutoTokenizer")
    @patch("caremap.llm_client.AutoModelForCausalLM")
    @patch("caremap.llm_client.pick_device")
    @patch("caremap.llm_client.pick_dtype")
    def test_includes_system_prompt_when_provided(self, mock_pick_dtype, mock_pick_device, mock_model_cls, mock_tokenizer_cls, mock_pipeline, mock_image):
        """Test that system prompt is included in messages."""
        mock_pick_device.return_value = torch.device("cpu")
        mock_pick_dtype.return_value = torch.float32

        mock_tokenizer = MagicMock()
        mock_tokenizer.pad_token_id = 1
        mock_tokenizer_cls.from_pretrained.return_value = mock_tokenizer

        mock_model = MagicMock()
        mock_model.to.return_value = mock_model
        mock_model_cls.from_pretrained.return_value = mock_model

        mock_pipe = MagicMock()
        mock_pipe.return_value = [{"generated_text": [{"content": "Response"}]}]
        mock_pipeline.return_value = mock_pipe

        client = MedGemmaClient(model_id="test/model", device="cpu", enable_multimodal=True)

        mock_pil_img = MagicMock()
        client.generate_with_images(
            "What is this?",
            [mock_pil_img],
            system_prompt="You are a helpful assistant."
        )

        # Check that pipeline was called with system message
        call_args = mock_pipe.call_args
        messages = call_args[1]["text"]
        assert len(messages) == 2  # system + user
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are a helpful assistant."

    @patch("caremap.llm_client.PIL_AVAILABLE", False)
    @patch("caremap.llm_client.hf_pipeline")
    @patch("caremap.llm_client.PIPELINE_AVAILABLE", True)
    @patch("caremap.llm_client.AutoTokenizer")
    @patch("caremap.llm_client.AutoModelForCausalLM")
    @patch("caremap.llm_client.pick_device")
    @patch("caremap.llm_client.pick_dtype")
    def test_raises_when_pil_not_available_at_runtime(self, mock_pick_dtype, mock_pick_device, mock_model_cls, mock_tokenizer_cls, mock_pipeline):
        """Test that RuntimeError is raised when PIL not available during generate_with_images."""
        mock_pick_device.return_value = torch.device("cpu")
        mock_pick_dtype.return_value = torch.float32

        mock_tokenizer = MagicMock()
        mock_tokenizer.pad_token_id = 1
        mock_tokenizer_cls.from_pretrained.return_value = mock_tokenizer

        mock_model = MagicMock()
        mock_model.to.return_value = mock_model
        mock_model_cls.from_pretrained.return_value = mock_model

        # Create client (multimodal won't be enabled since PIL_AVAILABLE=False)
        client = MedGemmaClient(model_id="test/model", device="cpu")
        # Manually set pipeline to simulate a broken state
        client._multimodal_pipe = MagicMock()

        with pytest.raises(RuntimeError, match="PIL.*required"):
            client.generate_with_images("What is this?", ["image.png"])


class TestInitMultimodalPipeline:
    """Tests for _init_multimodal_pipeline method."""

    @patch("caremap.llm_client.PIPELINE_AVAILABLE", False)
    @patch("caremap.llm_client.AutoTokenizer")
    @patch("caremap.llm_client.AutoModelForCausalLM")
    @patch("caremap.llm_client.pick_device")
    @patch("caremap.llm_client.pick_dtype")
    def test_raises_when_multimodal_not_available(self, mock_pick_dtype, mock_pick_device, mock_model_cls, mock_tokenizer_cls):
        """Test that RuntimeError is raised when calling _init_multimodal_pipeline without transformers."""
        mock_pick_device.return_value = torch.device("cpu")
        mock_pick_dtype.return_value = torch.float32

        mock_tokenizer = MagicMock()
        mock_tokenizer.pad_token_id = 1
        mock_tokenizer_cls.from_pretrained.return_value = mock_tokenizer

        mock_model = MagicMock()
        mock_model.to.return_value = mock_model
        mock_model_cls.from_pretrained.return_value = mock_model

        # Create client without multimodal (since dependency is missing)
        client = MedGemmaClient(model_id="test/model", device="cpu")

        # Directly calling _init_multimodal_pipeline should raise
        with pytest.raises(RuntimeError, match="Multimodal support requires transformers"):
            client._init_multimodal_pipeline()

    @patch("caremap.llm_client.PIPELINE_AVAILABLE", True)
    @patch("caremap.llm_client.PIL_AVAILABLE", False)
    @patch("caremap.llm_client.AutoTokenizer")
    @patch("caremap.llm_client.AutoModelForCausalLM")
    @patch("caremap.llm_client.pick_device")
    @patch("caremap.llm_client.pick_dtype")
    def test_raises_when_pil_not_available(self, mock_pick_dtype, mock_pick_device, mock_model_cls, mock_tokenizer_cls):
        """Test that RuntimeError is raised when calling _init_multimodal_pipeline without PIL."""
        mock_pick_device.return_value = torch.device("cpu")
        mock_pick_dtype.return_value = torch.float32

        mock_tokenizer = MagicMock()
        mock_tokenizer.pad_token_id = 1
        mock_tokenizer_cls.from_pretrained.return_value = mock_tokenizer

        mock_model = MagicMock()
        mock_model.to.return_value = mock_model
        mock_model_cls.from_pretrained.return_value = mock_model

        # Create client without multimodal (since PIL is missing)
        client = MedGemmaClient(model_id="test/model", device="cpu")

        # Directly calling _init_multimodal_pipeline should raise
        with pytest.raises(RuntimeError, match="Multimodal support requires PIL"):
            client._init_multimodal_pipeline()

    @patch("caremap.llm_client.hf_pipeline")
    @patch("caremap.llm_client.PIPELINE_AVAILABLE", True)
    @patch("caremap.llm_client.PIL_AVAILABLE", True)
    @patch("caremap.llm_client.AutoTokenizer")
    @patch("caremap.llm_client.AutoModelForCausalLM")
    @patch("caremap.llm_client.pick_device")
    @patch("caremap.llm_client.pick_dtype")
    def test_initializes_pipeline_on_cpu(self, mock_pick_dtype, mock_pick_device, mock_model_cls, mock_tokenizer_cls, mock_pipeline):
        """Test that multimodal pipeline is initialized correctly on CPU."""
        mock_pick_device.return_value = torch.device("cpu")
        mock_pick_dtype.return_value = torch.float32

        mock_tokenizer = MagicMock()
        mock_tokenizer.pad_token_id = 1
        mock_tokenizer_cls.from_pretrained.return_value = mock_tokenizer

        mock_model = MagicMock()
        mock_model.to.return_value = mock_model
        mock_model_cls.from_pretrained.return_value = mock_model

        mock_pipeline.return_value = MagicMock()

        client = MedGemmaClient(model_id="test/model", device="cpu", enable_multimodal=True)

        assert client.supports_multimodal is True
        mock_pipeline.assert_called_once_with(
            task="image-text-to-text",
            model=mock_model.to.return_value,
            tokenizer=mock_tokenizer,
        )

    @patch("caremap.llm_client.hf_pipeline")
    @patch("caremap.llm_client.PIPELINE_AVAILABLE", True)
    @patch("caremap.llm_client.PIL_AVAILABLE", True)
    @patch("caremap.llm_client.AutoTokenizer")
    @patch("caremap.llm_client.AutoModelForCausalLM")
    @patch("caremap.llm_client.pick_device")
    @patch("caremap.llm_client.pick_dtype")
    def test_initializes_pipeline_on_cuda(self, mock_pick_dtype, mock_pick_device, mock_model_cls, mock_tokenizer_cls, mock_pipeline):
        """Test that multimodal pipeline is initialized correctly on CUDA."""
        mock_pick_device.return_value = torch.device("cuda")
        mock_pick_dtype.return_value = torch.float16

        mock_tokenizer = MagicMock()
        mock_tokenizer.pad_token_id = 1
        mock_tokenizer_cls.from_pretrained.return_value = mock_tokenizer

        mock_model = MagicMock()
        mock_model.to.return_value = mock_model
        mock_model_cls.from_pretrained.return_value = mock_model

        mock_pipeline.return_value = MagicMock()

        client = MedGemmaClient(model_id="test/model", device="cuda", enable_multimodal=True)

        mock_pipeline.assert_called_once_with(
            task="image-text-to-text",
            model=mock_model.to.return_value,
            tokenizer=mock_tokenizer,
        )

    @patch("caremap.llm_client.hf_pipeline")
    @patch("caremap.llm_client.PIPELINE_AVAILABLE", True)
    @patch("caremap.llm_client.PIL_AVAILABLE", True)
    @patch("caremap.llm_client.AutoTokenizer")
    @patch("caremap.llm_client.AutoModelForCausalLM")
    @patch("caremap.llm_client.pick_device")
    @patch("caremap.llm_client.pick_dtype")
    def test_mps_falls_back_to_cpu_for_pipeline(self, mock_pick_dtype, mock_pick_device, mock_model_cls, mock_tokenizer_cls, mock_pipeline):
        """Test that MPS device falls back to CPU for multimodal pipeline."""
        mock_pick_device.return_value = torch.device("mps")
        mock_pick_dtype.return_value = torch.float16

        mock_tokenizer = MagicMock()
        mock_tokenizer.pad_token_id = 1
        mock_tokenizer_cls.from_pretrained.return_value = mock_tokenizer

        mock_model = MagicMock()
        mock_model.to.return_value = mock_model
        mock_model_cls.from_pretrained.return_value = mock_model

        mock_pipeline.return_value = MagicMock()

        client = MedGemmaClient(model_id="test/model", device="mps", enable_multimodal=True)

        mock_pipeline.assert_called_once_with(
            task="image-text-to-text",
            model=mock_model.to.return_value,
            tokenizer=mock_tokenizer,
        )


class TestImagingSystemPrompt:
    """Tests for IMAGING_SYSTEM_PROMPT constant."""

    def test_imaging_system_prompt_exists(self):
        from caremap.llm_client import IMAGING_SYSTEM_PROMPT
        assert IMAGING_SYSTEM_PROMPT is not None
        assert len(IMAGING_SYSTEM_PROMPT) > 0

    def test_imaging_system_prompt_contains_safety_rules(self):
        from caremap.llm_client import IMAGING_SYSTEM_PROMPT
        prompt_lower = IMAGING_SYSTEM_PROMPT.lower()
        assert "plain language" in prompt_lower
        assert "diagnose" in prompt_lower
        assert "doctor" in prompt_lower
