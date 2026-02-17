from accounts.models import Carbon


def carbon_context(request):
    carbon_id = request.session.get("carbon_id")
    if carbon_id:
        try:
            carbon = Carbon.objects.get(id=carbon_id, is_active=True)
            return {"logged_in_carbon": carbon}
        except Carbon.DoesNotExist:
            pass
    return {"logged_in_carbon": None}
