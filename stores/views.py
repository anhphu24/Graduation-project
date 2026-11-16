from django.shortcuts import redirect


def dashboard(request):
    # The canonical staff dashboard performs authentication and Membership checks.
    return redirect('market:staff')


def product_form(request):
    # Reuse the real, permission-checked lot registration workflow.
    return redirect('market:lot_new')
