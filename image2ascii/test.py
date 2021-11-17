from pathlib import Path

from PIL.Image import Image

from image2ascii.core import Image2ASCII


def test():
    """
    I know this is not a serious test whatsoever. It's mostly for me to step
    through with a debugger, checking so everything runs alright.
    """
    filename = Path(__file__).parent / "../hej.jpg"
    i2a = Image2ASCII()
    try:
        i2a.render()
    except ValueError as e:
        print(e)
    i2a.load(filename)
    assert isinstance(i2a.image, Image)
    assert i2a.image.width <= 2000 and i2a.image.height <= 2000
    assert i2a.image.mode == "RGBA"

    print(i2a.render())
    assert i2a.output is not None

    i2a.color_settings(color=True, invert=True)
    assert i2a.output is None
    # Should be in colour with inverted bool values
    print(i2a.render())
    assert i2a.output is not None

    i2a.size_settings(ascii_width=60, crop=True)
    assert i2a.output is None
    # Should be cropped and 60 chars wide
    print(i2a.render())
    assert i2a.output is not None

    i2a.quality_settings(quality=1)
    assert i2a.output is None
    # Should be cropped and 60 chars wide, and mostly dollar signs
    print(i2a.render())
    assert i2a.output is not None

    i2a.size_settings(ascii_width=80)
    i2a.quality_settings(quality=5)
    assert i2a.output is None
    # Should still be cropped but 80 chars wide and more detail
    print(i2a.render())


if __name__ == "__main__":
    test()
