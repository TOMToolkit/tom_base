from tom_targets.models import TargetList

BOOTSTRAP_COLORS = [
    'var(--red)',
    'var(--teal)',
    'var(--orange)',
    'var(--indigo)',
    'var(--pink)',
    'var(--green)',
    'var(--cyan)',
    'var(--purple)',
    'var(--blue)',
]


def target_list_color(target_list: TargetList) -> str:
    return BOOTSTRAP_COLORS[target_list.pk % len(BOOTSTRAP_COLORS)]
