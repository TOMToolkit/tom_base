from tom_common.forms import CustomUserCreationForm


class RegistrationApprovalForm(CustomUserCreationForm):
    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_active = False
        if self.cleaned_data['password1']:  # TODO: what is this?
            user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
            self.save_m2m()

        return user


# TODO: how will groups be handled in this registration flow? request group membership?
class OpenRegistrationForm(CustomUserCreationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop('groups')
