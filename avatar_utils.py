from PIL import Image


def get_avatar_zoom(user_info):
    try:
        return max(1.0, min(3.0, float(user_info.get("avatar_zoom", 1.0))))
    except (AttributeError, TypeError, ValueError):
        return 1.0


def get_avatar_focus(user_info):
    try:
        focus_x = max(0.0, min(1.0, float(user_info.get("avatar_focus_x", 0.5))))
        focus_y = max(0.0, min(1.0, float(user_info.get("avatar_focus_y", 0.5))))
        return focus_x, focus_y
    except (AttributeError, TypeError, ValueError):
        return 0.5, 0.5


def crop_avatar(image, zoom=1.0, focus_x=0.5, focus_y=0.5):
    image = image.convert("RGB")
    zoom = max(1.0, min(3.0, float(zoom)))
    focus_x = max(0.0, min(1.0, float(focus_x)))
    focus_y = max(0.0, min(1.0, float(focus_y)))
    if zoom <= 1.0:
        return image

    width, height = image.size
    crop_width = max(1, int(width / zoom))
    crop_height = max(1, int(height / zoom))
    left = max(0, min(width - crop_width, int((width - crop_width) * focus_x)))
    top = max(0, min(height - crop_height, int((height - crop_height) * focus_y)))
    return image.crop((left, top, left + crop_width, top + crop_height))
