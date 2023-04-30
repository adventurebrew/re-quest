# Sounder
**Sounder** can do more or less anything that you'd like with Sierra's SCI sound format.

# Installation
Use can either download Windows executable from *Releases*, or prepare Python environment manually:

    conda create -n sounder -c conda-forge mido pyaudio av python=3.10
    conda activate sounder
    pip install python-rtmidi wxpython==4.2.0 gooey

Or maybe even simpler:

    pip install -e .


And just run

    python sounder.py --help

# User guide
You can read it either by:
- Run GUI mode, under *Help* menu
- Locally open `usage.html` file in your browser
- Open [usage.html](https://htmlpreview.github.io/?https://github.com/adventurebrew/re-quest/blob/master/tools/sci/sounder/usage.html)

# Specification
The work was based on the specs at:

https://wiki.scummvm.org/index.php/SCI/Specifications/Sound/SCI0_Resource_Format  
https://sciprogramming.com/community/index.php?topic=2072

# Keep In Touch
*Sounder* is still young, and probably has some bugs and problems. Please, update me with any problem or issue. I'd
also like to hear if you're just using it, and you're satisfied :-)

I can be reached in:
- [https://github.com/adventurebrew/re-quest/issues](https://github.com/adventurebrew/re-quest/issues) (you can open an "issue" even for a non bug)
- ZvikaZ at [https://sciprogramming.com](https://sciprogramming.com) forums (or PM)
- ZvikaZ at ScummVM's Discord server



