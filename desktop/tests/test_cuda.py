"""CUDA 标记的测试：无 GPU 环境自动跳过（CI 中 -m "not cuda" 过滤）。"""
import pytest

pytestmark = pytest.mark.cuda


def test_cuda_available():
    torch = pytest.importorskip("torch")
    assert torch.cuda.is_available()