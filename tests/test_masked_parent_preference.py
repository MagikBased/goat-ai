"""Bad-action suppression should preserve the parent's other action rankings."""

import pytest
import torch

from goat_ai.training.parent_kl import masked_parent_distribution


def test_masked_parent_excludes_bad_action_and_preserves_good_ratio() -> None:
    logits = torch.tensor([3.0, 1.0, 0.0])
    target = masked_parent_distribution(logits, (0,))
    assert target[0].item() == 0
    assert target.sum().item() == pytest.approx(1)
    assert (target[1] / target[2]).item() == pytest.approx(torch.exp(logits[1]).item())

    student = torch.nn.Parameter(logits.clone())
    optimizer = torch.optim.SGD([student], lr=0.5)
    before = torch.softmax(student.detach(), dim=0)[0].item()
    optimizer.zero_grad()
    (-(target * torch.log_softmax(student, dim=0)).sum()).backward()
    optimizer.step()
    assert torch.softmax(student.detach(), dim=0)[0].item() < before


@pytest.mark.parametrize("indices", [(), (0, 1), (0, 0), (2,), (True,)])
def test_masked_parent_requires_proper_unique_integer_subset(indices) -> None:
    with pytest.raises(ValueError):
        masked_parent_distribution(torch.tensor([1.0, 2.0]), indices)
