# Simple masking for what is shown on screen. The stored anonymized
# values (ANON_1021 and the like) are made in the next step.


def mask_name(name):
    if not name:
        return "***"
    return name[0] + "***"


def mask_contact(contact):
    digits = "".join(ch for ch in (contact or "") if ch.isdigit())
    return "XXX-XXX-" + digits[-4:]


def mask_diagnosis():
    return "***"


def show_name(name, anonymized_name, can_view_raw):
    if can_view_raw:
        return name
    if anonymized_name:
        return anonymized_name
    return mask_name(name)


def show_contact(contact, anonymized_contact, can_view_raw):
    if can_view_raw:
        return contact
    if anonymized_contact:
        return anonymized_contact
    return mask_contact(contact)
