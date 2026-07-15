from tom_targets.models import TargetList

BOOTSTRAP_COLORS = [
    'var(--bs-red)',
    'var(--bs-teal)',
    'var(--bs-orange)',
    'var(--bs-indigo)',
    'var(--bs-pink)',
    'var(--bs-green)',
    'var(--bs-cyan)',
    'var(--bs-purple)',
    'var(--bs-blue)',
]


def target_list_color(target_list: TargetList) -> str:
    return BOOTSTRAP_COLORS[target_list.pk % len(BOOTSTRAP_COLORS)]
