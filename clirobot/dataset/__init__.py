"""Dataset processing, pruning, annotation parsing, and splitting tools for LeRobot."""

from clirobot.dataset.prune import prune_dataset, PruneResult
from clirobot.dataset.annotations import (
    load_dataset_annotations,
    inspect_annotations,
    AnnotationSummary,
    sanitize_dataset_metadata,
)
from clirobot.dataset.split import (
    split_dataset,
    BaseAnnotationSplitter,
    SubtaskSplitter,
    TaskAugSplitter,
    PlanSplitter,
    VQASplitter,
    SpeechSplitter,
    EpisodeSegment,
    SplitResult,
    get_splitter,
    list_splitters,
)

__all__ = [
    "prune_dataset",
    "PruneResult",
    "load_dataset_annotations",
    "inspect_annotations",
    "AnnotationSummary",
    "sanitize_dataset_metadata",
    "split_dataset",
    "BaseAnnotationSplitter",
    "SubtaskSplitter",
    "TaskAugSplitter",
    "PlanSplitter",
    "VQASplitter",
    "SpeechSplitter",
    "EpisodeSegment",
    "SplitResult",
    "get_splitter",
    "list_splitters",
]
