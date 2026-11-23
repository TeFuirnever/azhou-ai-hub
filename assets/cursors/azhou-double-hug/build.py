#!/usr/bin/env python3
"""Build Azhou Double Hug from its two approved source atlases."""

import argparse
import io
import math
from pathlib import Path
import plistlib

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent
FILENAME = 'Azhou-Double-Hug-3.6.1.cape'
IDENTIFIER = 'lab.azhou.cursors.doublehug.v361'
S=4
N=32*S
D='#59301f'; C='#fff0d9'; O='#f59443'
CG='com.apple.coregraphics.'; NS='com.apple.cursor.'
def blank():return Image.new('RGBA',(N,N))
def pts(points):return [(round(x*S),round(y*S)) for x,y in points]
def poly(im,points,color,outline=D,w=1.1):
    d=ImageDraw.Draw(im); xy=pts(points);d.polygon(xy,fill=color)
    if outline:d.line(xy+[xy[0]],fill=outline,width=round(w*S),joint='curve')
def circ(im,x,y,r,color,outline=None,w=1):
    ImageDraw.Draw(im).ellipse(((x-r)*S,(y-r)*S,(x+r)*S,(y+r)*S),fill=color,outline=outline,width=round(w*S))
def line(im,points,col,w):
    ImageDraw.Draw(im).line(pts(points),fill=col,width=round(w*S),joint='curve')
    for x,y in [points[0],points[-1]]:circ(im,x,y,w/2,col)
def stroke(im,p,fill=C,w=2.5):
    line(im,p,D,w+1.8);line(im,p,fill,w)
def arc(im,x,y,r,start,end,col,width):
    p=[(x+r*math.cos(math.radians(start+(end-start)*i/32)),y+r*math.sin(math.radians(start+(end-start)*i/32))) for i in range(33)]
    line(im,p,col,width)
def ring(im,x,y,r,angle):
    circ(im,x,y,r+1.7,None,D,1.35);circ(im,x,y,r-1.1,None,D,1.15)
    arc(im,x,y,r,0,360,C,2.4);arc(im,x,y,r,angle,angle+78,O,2.6)
approved = Image.open(ROOT / 'hug-source.png').convert('RGBA')
companion_atlas = Image.open(ROOT / 'poses-source.png').convert('RGBA')


def downsample(image, size):
    return image.convert('RGBa').resize(size, Image.Resampling.LANCZOS).convert('RGBA')


def sprite(image, columns, rows, column, row, bounds=None):
    w, h = image.size
    cell = image.crop(bounds or (w*column//columns, h*row//rows, w*(column+1)//columns, h*(row+1)//rows))
    solid = cell.getchannel('A').point(lambda value: 255 if value >= 64 else 0)
    box = solid.getbbox()
    if not box:
        raise ValueError(f'Empty sprite at {column}, {row}')
    return cell.crop(box)


def place(sprite_image, height, center_x, top, max_width=N-5):
    scale = min(height / sprite_image.height, max_width / sprite_image.width)
    fitted = downsample(sprite_image, (round(sprite_image.width*scale), round(sprite_image.height*scale)))
    frame = blank()
    frame.alpha_composite(fitted, (round(center_x-fitted.width/2), top))
    return frame


# Same upper face and camera angle across the approved motion strip.
sweep = sprite(approved, 3, 2, 0, 0)
hug = sprite(approved, 3, 2, 0, 1)
portrait = sprite(companion_atlas,2,2,0,0)
open_hands = sprite(companion_atlas,2,2,1,0)
clock = sprite(companion_atlas,2,2,0,1)
finger = sprite(companion_atlas,2,2,1,1)
poses = {
    # Match the accepted portrait's alpha rounding in the two exported scales.
    'arrow': place(portrait, 70, 92, 51, 67).transform(
        (N, N), Image.Transform.AFFINE, (1, 0, 0, 0, 1, 0), Image.Resampling.BICUBIC,
    ),
    'point': place(finger, 72, 92, 50, 68),
    'open': place(open_hands, 117, 64, 5, 116),
    'sweep': place(sweep, 116, 64, 5, 116),
    'hug': place(hug, 116, 64, 5, 116),
    'clock': place(clock, 65, 94, 56, 61),
}
def softened_polygon(vertices, inset, tip_inset=None):
    # Round each vertex with a short quadratic arc. The edge remains straight
    # between corners, so the silhouette survives downsampling at 1x.
    def near(point, neighbor, corner_inset):
        length = math.dist(point, neighbor)
        return tuple(a + (b-a) * min(corner_inset/length, .4)
                     for a,b in zip(point, neighbor))
    points = []
    for i, vertex in enumerate(vertices):
        corner_inset = tip_inset if i == 0 and tip_inset is not None else inset
        entry = near(vertex, vertices[i-1], corner_inset)
        exit = near(vertex, vertices[(i+1) % len(vertices)], corner_inset)
        for step in range(9):
            t = step/8
            points.append(tuple((1-t)**2*a + 2*t*(1-t)*b + t*t*c
                                for a,b,c in zip(entry, vertex, exit)))
    return points


def pointer_surface(top, bottom):
    light, shade = (bytes.fromhex(color) for color in (top, bottom))
    gradient = Image.new('RGBA', (1, N))
    colors = []
    for y in range(N):
        blend = max(0, min(1, (y/S - 4)/17))
        colors.append(tuple(round(a + (b-a)*blend) for a,b in zip(light, shade)) + (255,))
    gradient.putdata(colors)
    return gradient.resize((N, N))


cream_pointer = pointer_surface('fffcf3', 'ffdfb7')
orange_pointer = pointer_surface('ffd495', 'f48837')


def locator(frame, link=False):
    # Keep the triangle inside the left half of the portrait's visual space.
    # Only the shoulder and base get a generous rounding, so the hotspot
    # remains covered at the tip.
    hull = [(2.0, 2.0), (20.8, 12.4), (8.0, 22.7)]
    shape = Image.new('L', (N, N))
    ImageDraw.Draw(shape).polygon(pts(softened_polygon(hull, 2.5, tip_inset=.7)), fill=255)
    edge = shape.filter(ImageFilter.MaxFilter(7))
    rim = Image.new('RGBA', (N, N), '#70432b')
    rim.putalpha(edge)
    frame.alpha_composite(rim)

    surface = (orange_pointer if link else cream_pointer).copy()
    surface.putalpha(shape)
    frame.alpha_composite(surface)

    # Rounded bevel stays inside the triangle with room around the tip.
    bevel = blank()
    band = [(8.4, 19.8), (18.5, 12.6), (11.3, 17.0), (9.1, 17.5)]
    poly(bevel, softened_polygon(band, .8), '#d27a42' if link else '#e9ab76', None)
    if link:
        line(bevel, [(4.9, 5.2), (10.9, 8.6)], '#ffeccf', .62)
    frame.alpha_composite(bevel)


def arrow():
    frame = poses['arrow'].copy()
    locator(frame)
    return frame


def beam(t=0):
    frame = blank()
    stroke(frame, [(16,5.9),(16,26.1)], C, 2.3)
    stroke(frame, [(12.5,26.6),(19.5,26.6)], C, 1.7)
    # Small fox-tail tip at the top, with a stable text hotspot.
    sway = .8*math.sin(2*math.pi*t)
    vertices = [(11.5,5.5),(13.2+sway,2.7),(16.6,4.3),
                (20.7+sway,3.1),(18.2,7.2),(14.2,7.1)]
    poly(frame, softened_polygon(vertices, .65), O, D, 1.0)
    line(frame,[(12.9,5.4),(15.3,5.9)],C,.8)
    return frame


def dirig(angle,both=True,divider=False):
    frame = blank()
    rad = math.radians(angle)
    def tr(x,y):
        return (16+x*math.cos(rad)-y*math.sin(rad),
                16+x*math.sin(rad)+y*math.cos(rad))
    for sign in ([1,-1] if both else [1]):
        shape = [(12.2,0),(5.7,-3.7),(5.7,3.7)]
        poly(frame, softened_polygon([tr(sign*x,y) for x,y in shape], .9), C, D, 1.1)
        poly(frame,[tr(sign*x,y) for x,y in [(10.6,0),(7.2,-1.4),(7.2,1.4)]],O,None)
    if not both:
        stroke(frame,[tr(-11,0),tr(-6.5,0)],C,1.9)
    if divider:
        stroke(frame,[tr(0,-3.8),tr(0,3.8)],C,1.5)
    return frame


def move():
    frame = blank()
    for points in ([(6,16),(26,16)],[(16,6),(16,26)]):
        line(frame,points,D,5.1)
    for points in ([(6,16),(26,16)],[(16,6),(16,26)]):
        line(frame,points,C,3.2)
    circ(frame,16,16,1.7,O)
    return frame


def badge(role,t=0):
    if role=='point':
        frame = poses['point'].copy()
        locator(frame,link=True)
        arc(frame,24.4,6.5,3.1,-95+36*math.sin(t*math.tau),75,O,1.65)
        return frame
    frame = arrow()
    x, y = 24.6, 7.0
    circ(frame, x, y, 4.3, C, D, 1.1)
    accent = '#9c4c23'
    if role=='copy':
        line(frame,[(x-2.2,y),(x+2.2,y)],accent,1.35)
        line(frame,[(x,y-2.2),(x,y+2.2)],accent,1.35)
    elif role=='alias':
        line(frame,[(x-2.1,y+2),(x+1.8,y-1.9),(x-1.2,y-1.9)],accent,1.2)
        line(frame,[(x+1.8,y-1.9),(x+1.8,y+1)],accent,1.2)
    elif role=='ctx':
        for yy in (y-1.5,y,y+1.5):
            line(frame,[(x-1.6,yy),(x+1.6,yy)],D,.8)
    else:
        arc(frame, x, y-1.3, 1.16, 185, 405, D, .76)
        line(frame, [(x+.82,y-.48),(x,y+.27),(x,y+.9)], D, .76)
        circ(frame, x, y+2.05, .39, D)
    return frame


def wait(t,busy=False):
    frame = poses['clock'].copy()
    if busy:
        locator(frame)
        ring(frame, 9.0, 25.4, 3.8, 360*t-90)
    else:
        ring(frame, 11, 12.4, 7.6, 360*t-90)
    return frame


def counting(t,sign):
    a=blank();ring(a,16,16,9.6,360*t-90)
    if sign in ('up','both'):poly(a,[(12,16 if sign=='both' else 18),(16,11),(20,16 if sign=='both' else 18)],O,D,1.1)
    if sign in ('down','both'):poly(a,[(12,17 if sign=='both' else 14),(16,22 if sign=='both' else 21),(20,17 if sign=='both' else 14)],C,D,1.1)
    return a
def cross():
    a=blank()
    for dx,dy in [(1,0),(-1,0),(0,1),(0,-1)]:
        stroke(a,[(16+4*dx,16+4*dy),(16+11*dx,16+11*dy)],C,1.8)
    circ(a,16,16,1.4,O,D,.6);return a
def stop():
    a=blank();circ(a,16,16,10.3,C,D,1.6)
    stroke(a,[(10,10),(22,22)],O,2.8);return a


def encode(frames, seconds_per_frame=1, hotspot=(16, 16)):
    representations = []
    for n in (32, 64):
        strip = Image.new('RGBA', (n, n*len(frames)))
        for i, frame in enumerate(frames):
            strip.paste(downsample(frame, (n, n)), (0, n*i))
        with io.BytesIO() as buffer:
            strip.save(buffer, 'PNG', optimize=True)
            representations.append(buffer.getvalue())
    return {
        'FrameCount': len(frames), 'FrameDuration': float(seconds_per_frame),
        'HotSpotX': float(hotspot[0]), 'HotSpotY': float(hotspot[1]),
        'PointsWide': 32.0, 'PointsHigh': 32.0,
        'Representations': representations,
    }


def build_cape():
    roles = {}

    def add(keys, frames, seconds_per_frame=1, hotspot=(16, 16)):
        data = encode(frames, seconds_per_frame, hotspot)
        for key in keys:
            roles[key] = data

    # The arrow tip is the hotspot in every directional-arrow state.
    tip = (2.5, 2.5)
    grip = (16, 21)
    add([CG+'Arrow', CG+'ArrowS'], [arrow()], hotspot=tip)
    add([CG+'ArrowCtx'], [badge('ctx')], hotspot=tip)

    # Preselect the same frames used by 3.6 before encoding either PNG scale.
    phases = [i/24 for i in range(24)]
    text_phases = [(i*32//24)/32 for i in range(24)]
    ibeams = [beam(t) for t in text_phases]
    add([CG+'IBeam', CG+'IBeamXOR', CG+'IBeamS'], ibeams, .05*32/24)
    vertical_text = [frame.transpose(Image.Transpose.ROTATE_90) for frame in ibeams]
    add([NS+'26'], vertical_text, .05*32/24)
    add([CG+'Move', NS+'39'], [move()])
    add([CG+'Wait'], [wait(t) for t in phases], 1/24)
    add([NS+'4'], [wait(t, busy=True) for t in phases], 1/24, tip)
    add([NS+'12'], [poses['open']], hotspot=grip)
    add([NS+'11'], [poses['sweep']] + [poses['hug']]*23, .12, grip)
    add([NS+'13'], [badge('point', t) for t in phases], .05, tip)
    for key, sign in [('14','up'), ('15','down'), ('16','both')]:
        add([NS+key], [counting(t, sign) for t in text_phases], 1/24)
    for key, kind in [('2','alias'), ('5','copy'), ('40','help')]:
        add([NS+key], [badge(kind)], hotspot=tip)
    add([NS+'3'], [stop()])
    add([NS+'7', NS+'20'], [cross()])

    resize_roles = [
        (17,180,False,True), (18,0,False,True), (19,0,True,True),
        (21,-90,False,True), (22,90,False,True), (23,90,True,True),
        (27,0,False,False), (28,0,True,False), (29,-45,False,False),
        (30,-45,True,False), (31,-90,False,False), (32,90,True,False),
        (33,-135,False,False), (34,45,True,False), (35,45,False,False),
        (36,90,False,False), (37,135,False,False), (38,180,False,False),
    ]
    for key, angle, both, divider in resize_roles:
        add([NS+str(key)], [dirig(angle, both, divider)])

    return {
        'Author': 'Azhou Agent Lab', 'CapeName': '百变阿舟 · 抱一下 3.6.1',
        'CapeVersion': 3.61, 'Cloud': False, 'HiDPI': True,
        'Identifier': IDENTIFIER, 'MinimumVersion': 2.0,
        'Version': 2.0, 'Cursors': roles,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/FILENAME)
    path = parser.parse_args().output
    path.write_bytes(plistlib.dumps(build_cape()))
    print(f'{path.name}: {path.stat().st_size:,} bytes')


if __name__ == '__main__':
    main()
