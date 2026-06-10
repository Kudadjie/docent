"""Research workflow action mixins: deep-research, lit, review, compare, draft, replicate, audit."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# The real Feynman entry points live on THIS module on purpose: tests (and any
# external code) patch `studio._research._run_feynman`, and the action modules
# delegate back here at call time. Do not remove these as "unused".
from docent.bundled_plugins.studio.feynman import (  # noqa: E402, F401
    FeynmanNotFoundError,
    _run_feynman,
    _summarize_feynman_error,
)

from ._research_actions_artifacts import ResearchArtifactActions  # noqa: E402
from ._research_actions_core import ResearchCoreActions  # noqa: E402
from ._research_helpers import (  # noqa: E402, F401
    _expand_citations,
    _extract_anchor_ids,
)


class ResearchMixin(ResearchCoreActions, ResearchArtifactActions):
    """Mixin providing research actions for StudioTool.

    Composed from two action modules; collect_actions() walks the MRO via
    dir(cls), so @action methods on the bases register exactly as before.
    """
