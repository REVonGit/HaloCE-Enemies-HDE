"""The ZScript and GLSL that build_pack.py and build_digsite.py write into the packs as-is, kept as files under
templates/ so they read (and diff) as the code they are: templates/zscript/*.zs is ZScript pasted into generated
classes, templates/shaders/*.fp is GLSL for GLDEFS hardware shaders.

    from templates import template
    STICKY_CODE = template('zscript/sticky.zs')     # the file's text, exactly
"""
import os
TEMPLATES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')


def template(name):
    """the text of templates/<name>, byte for byte (no newline translation)"""
    with open(os.path.join(TEMPLATES, name), encoding='utf-8', newline='') as f:
        return f.read()
