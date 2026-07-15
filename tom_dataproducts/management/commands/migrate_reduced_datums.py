from django.core.management.base import BaseCommand

from tom_dataproducts.models import (ReducedDatum, PhotometryReducedDatum,
                                     SpectroscopyReducedDatum, AstrometryReducedDatum)

BATCH_SIZE = 1000

BRIGHTNESS_FIELDS = ('brightness', 'magnitude', 'mag')
BRIGHTNESS_ERROR_FIELDS = ('brightness_error', 'error', 'magnitude_error', 'mag_error')
BANDPASS_FIELDS = ('bandpass', 'filter', 'band', 'f')


def _pop_first(d, keys, default=None):
    for key in keys:
        if key in d and d[key] is not None:
            return d[key]
    return default


def _run_batched(queryset, build_fn, TypedModel, dry_run, stdout):
    to_create = []
    pks_to_delete = []
    total_created = 0
    total_deleted = 0

    for rd in queryset.iterator(chunk_size=BATCH_SIZE):
        instance = build_fn(rd)
        to_create.append(instance)
        pks_to_delete.append(rd.pk)

        if len(to_create) >= BATCH_SIZE:
            if not dry_run:
                TypedModel.objects.bulk_create(to_create, ignore_conflicts=True)
                ReducedDatum.objects.filter(pk__in=pks_to_delete).delete()
            total_created += len(to_create)
            total_deleted += len(pks_to_delete)
            to_create = []
            pks_to_delete = []

    if to_create:
        if not dry_run:
            TypedModel.objects.bulk_create(to_create, ignore_conflicts=True)
            ReducedDatum.objects.filter(pk__in=pks_to_delete).delete()
        total_created += len(to_create)
        total_deleted += len(pks_to_delete)

    label = '[DRY RUN] Would migrate' if dry_run else 'Migrated'
    stdout.write(f'  {label} {total_created} {TypedModel.__name__} rows, deleted {total_deleted} ReducedDatum rows.')


def _build_photometry(rd):
    value = rd.value or {}
    return PhotometryReducedDatum(
        target_id=rd.target_id,
        data_product_id=rd.data_product_id,
        source_name=rd.source_name,
        source_location=rd.source_location,
        timestamp=rd.timestamp,
        telescope=rd.telescope or value.get('telescope', ''),
        instrument=rd.instrument or value.get('instrument', ''),
        brightness=_pop_first(value, BRIGHTNESS_FIELDS),
        brightness_error=_pop_first(value, BRIGHTNESS_ERROR_FIELDS),
        limit=value.get('limit'),
        unit=value.get('unit', ''),
        bandpass=_pop_first(value, BANDPASS_FIELDS, default=''),
    )


def _build_spectroscopy(rd):
    value = rd.value or {}
    return SpectroscopyReducedDatum(
        target_id=rd.target_id,
        data_product_id=rd.data_product_id,
        source_name=rd.source_name,
        source_location=rd.source_location,
        timestamp=rd.timestamp,
        telescope=rd.telescope or value.get('telescope', ''),
        instrument=rd.instrument or value.get('instrument', ''),
        flux=value.get('flux', []),
        wavelength=value.get('wavelength', []),
        error=value.get('error', value.get('flux_error', [])),
        flux_unit=value.get('flux_units', value.get('flux_unit', '')),
    )


def _build_astrometry(rd):
    value = rd.value or {}
    return AstrometryReducedDatum(
        target_id=rd.target_id,
        data_product_id=rd.data_product_id,
        source_name=rd.source_name,
        source_location=rd.source_location,
        timestamp=rd.timestamp,
        telescope=rd.telescope or value.get('telescope', ''),
        instrument=rd.instrument or value.get('instrument', ''),
        ra=value.get('ra'),
        dec=value.get('dec'),
        ra_error=value.get('ra_error'),
        dec_error=value.get('dec_error'),
        ra_error_units=value.get('ra_error_units', ''),
        dec_error_units=value.get('dec_error_units', ''),
    )


class Command(BaseCommand):
    help = """
        Migrates generic ReducedDatum rows into their concrete typed models
        (PhotometryReducedDatum, SpectroscopyReducedDatum, AstrometryReducedDatum)
        and deletes the originals. Run this once after deploying the reduceddatum refactor.
        Only necessary for TOMs that existed prior to v3.
        """

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report what would be migrated without writing any changes.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write('Dry run — no changes will be written.\n')

        steps = [
            ('photometry', ReducedDatum.objects.filter(data_type='photometry'),
             _build_photometry, PhotometryReducedDatum),
            ('spectroscopy', ReducedDatum.objects.filter(data_type='spectroscopy'),
             _build_spectroscopy, SpectroscopyReducedDatum),
            ('astrometry', ReducedDatum.objects.filter(data_type='astrometry'),
             _build_astrometry, AstrometryReducedDatum),
        ]

        for name, queryset, build_fn, TypedModel in steps:
            count = queryset.count()
            self.stdout.write(f'{name}: {count} rows to migrate.')
            if count:
                _run_batched(queryset, build_fn, TypedModel, dry_run, self.stdout)

        self.stdout.write(self.style.SUCCESS('Done.'))
