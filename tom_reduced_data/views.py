from io import StringIO

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic.base import RedirectView
from django.core.management import call_command
from django.http import HttpResponseRedirect
from django.contrib import messages


class UpdateReducedDataGroupingView(LoginRequiredMixin, RedirectView):
    def get(self, request, *args, **kwargs):
        target_id = request.GET.get('target_id', None)
        out = StringIO()
        if target_id:
            call_command('updatereduceddata', target_id=target_id, stdout=out)
        else:
            call_command('updatereduceddata', stdout=out)
        messages.info(request, out.getvalue())
        return HttpResponseRedirect(self.get_redirect_url(*args, **kwargs))

    def get_redirect_url(self):
        referer = self.request.META.get('HTTP_REFERER', '/')
        return referer
