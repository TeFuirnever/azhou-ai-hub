from PIL import Image,ImageDraw,ImageFont
from pathlib import Path
import math, io, plistlib, sys
root = Path(__file__).resolve().parent
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
def letter(im,x,y,text,size):
    f=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Rounded Bold.ttf',round(size*S))
    ImageDraw.Draw(im).text((x*S,y*S),text,font=f,fill=D,anchor='mm')

approved = Image.open(root / 'hug-source.png').convert('RGBA')
companion_atlas = Image.open(root / 'poses-source.png').convert('RGBA')


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
    'arrow': place(portrait, 93, 75, 29, 93),
    'point': place(finger, 94, 75, 28, 96),
    'open': place(open_hands, 117, 64, 5, 116),
    'sweep': place(sweep, 116, 64, 5, 116),
    'hug': place(hug, 116, 64, 5, 116),
    'clock': place(clock, 103, 76, 18, 96),
}
def shift(im,dx=0,dy=0,angle=0,center=None):
    if angle:im=im.rotate(angle,Image.Resampling.BICUBIC,center=center)
    return im.transform(im.size,Image.Transform.AFFINE,(1,0,-dx*S,0,1,-dy*S),Image.Resampling.BICUBIC)
def companion(t=0, pointing=False):
    base = poses['point' if pointing else 'arrow']
    if pointing:
        return base.copy()
    phase = max(0, min(1, (t-.63)/.22))
    nod = math.sin(math.pi*phase)**2
    return shift(base, dy=-.38*nod, angle=1.5*nod, center=(75,76))


def locator(frame):
    poly(frame,[(2.5,2.5),(13.4,8.2),(9.1,9.6),(6.7,14.5)],C,D,1.1)
    poly(frame,[(4.0,4.2),(10.6,7.6),(8.0,8.4),(6.6,11.0)],O,None)


def bot(t=0):
    frame = companion(t)
    locator(frame)
    return frame


def beam(t=0):
    a=blank()
    stroke(a,[(16,7.9),(16,24.7)],C,2.8)
    stroke(a,[(12.5,26),(16,24.7),(19.5,26)],C,2.0)
    # Tapered tail-tip nib pivots around the fixed top of the caret.
    shift=1.25*math.sin(2*math.pi*t)
    poly(a,[(12.3,7.9),(11.8+shift,3.2),(15.4,5.4),(19.4+shift,2.8),(18.8,7.3),(16,9.2)],O,D,1.15)
    return a
def dirig(angle,both=True,divider=False):
    a=blank();cy=16
    def tr(x,y):
        rad=math.radians(angle);return (16+x*math.cos(rad)-y*math.sin(rad),cy+x*math.sin(rad)+y*math.cos(rad))
    if not both:stroke(a,[tr(-5,0),tr(4,0)],C,2)
    for sign in ([1,-1] if both else [1]):
        shape=[(12,0),(6,-4.6),(6,-2),(3.2,-2),(3.2,2),(6,2),(6,4.6)]
        poly(a,[tr(sign*x,y) for x,y in shape],C,D,1.15)
        poly(a,[tr(sign*x,y) for x,y in [(11.2,0),(7,-2.7),(7,2.7)]],O,None)
    if divider:stroke(a,[tr(0,-3),tr(0,3)],C,1)
    return a
def move():
    a=blank()
    xy=[(16,3),(20,8),(17.7,8),(17.7,14.3),(24,14.3),(24,12),(29,16),(24,20),(24,17.7),(17.7,17.7),(17.7,24),(20,24),(16,29),(12,24),(14.3,24),(14.3,17.7),(8,17.7),(8,20),(3,16),(8,12),(8,14.3),(14.3,14.3),(14.3,8),(12,8)]
    poly(a,xy,C,D,1.2);circ(a,16,16,2.2,O)
    return a
def badge(role,t=0):
    if role=='point':
        a = companion(pointing=True)
        # The animation stays on the far side of the arrow tip.
        phase = (t*1.45) % 1
        if t < .64:
            overlay = blank()
            arc(overlay, 7.2, 6.9, 4.8+2*phase, -52, 20, O, 1.45)
            overlay.putalpha(overlay.getchannel('A').point(lambda value: round(value*(1-phase))))
            a.alpha_composite(overlay)
        locator(a)
        return a
    a = bot(t)
    x,y = 24.6,23.8
    circ(a,x,y,5.75,C,D,1.25)
    accent=tuple(round(v+(w-v)*(.5-.5*math.cos(2*math.pi*t))) for v,w in zip((111,56,16),(223,125,26)))
    if role=='copy':
        line(a,[(x-2.6,y),(x+2.6,y)],accent,1.5);line(a,[(x,y-2.6),(x,y+2.6)],accent,1.5)
    elif role=='alias':
        line(a,[(x-2.5,y+2),(x+2,y-2.5),(x-1.5,y-2.5)],accent,1.3);line(a,[(x+2,y-2.5),(x+2,y+1)],accent,1.3)
    elif role=='ctx':
        for yy in (y-2,y,y+2):line(a,[(x-2,yy),(x+2,yy)],D,1)
    else:letter(a,x,y,'?',8)
    return a

def wait(t,busy=False):
    a = poses['clock'].copy()
    # The watch stays stable while the activity mark rotates beside it.
    cy = 16 if busy else 12.5
    arc(a, 5.4, cy, 3.5, 0, 360, D, 2.8)
    arc(a, 5.4, cy, 3.5, 0, 360, C, 1.5)
    arc(a, 5.4, cy, 3.5, 360*t-90, 360*t-8, O, 1.6)
    if busy:
        poly(a,[(2.1,2.1),(10,5.9),(6.7,7.0),(5.1,10.9)],C,D,1.0)
    return a


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
def hugmotion():
    # Real pose change across two matched frames. Keep the selected illustration on screen during the hold.
    return [poses['sweep']]*2 + [poses['hug']]*118


sets={}; roles={}
def add(keys,frames,dt=1,hot=(16,16)):
    entry={'FrameCount':len(frames),'FrameDuration':float(dt),'HotSpotX':float(hot[0]),'HotSpotY':float(hot[1]),'PointsWide':32.,'PointsHigh':32.,'Representations':[]}
    for n in (32,64):
        tile=Image.new('RGBA',(n,n*len(frames)))
        for i,f in enumerate(frames):
            tile.paste(downsample(f,(n,n)),(0,n*i))
        buf=io.BytesIO();tile.save(buf,'PNG',optimize=True);entry['Representations'].append(buf.getvalue())
    for k in keys:
        roles[k]=entry;sets[k]=(frames,dt)
add([CG+'Arrow',CG+'ArrowS'],[bot(i/96) for i in range(96)],.05,(2.5,2.5))
add([CG+'ArrowCtx'],[badge('ctx',i/48) for i in range(48)],.05,(2.5,2.5))
ibeams=[beam(i/32) for i in range(32)]
add([CG+'IBeam',CG+'IBeamXOR',CG+'IBeamS'],ibeams,.05)
add([NS+'26'],[f.transpose(Image.Transpose.ROTATE_90) for f in ibeams],.05)
add([CG+'Move',NS+'39'],[move()])
add([CG+'Wait'],[wait(i/48) for i in range(48)],1/48)
add([NS+'4'],[wait(i/48,True) for i in range(48)],1/48,(2,2))
add([NS+'12'],[poses['open']],hot=(16,21))
add([NS+'11'],hugmotion(),.04,(16,21))
add([NS+'13'],[badge('point',i/24) for i in range(24)],.05,(2.5,2.5))
for k,sign in [('14','up'),('15','down'),('16','both')]:
    add([NS+k],[counting(i/32,sign) for i in range(32)],1/32)
for k,kind in [('2','alias'),('5','copy'),('40','help')]:
    add([NS+k],[badge(kind,i/48) for i in range(48)],.05,(2.5,2.5))
add([NS+'3'],[stop()])
add([NS+'7',NS+'20'],[cross()])
for k,angle,both,divider in [(17,180,False,True),(18,0,False,True),(19,0,True,True),(21,-90,False,True),(22,90,False,True),(23,90,True,True),(27,0,False,False),(28,0,True,False),(29,-45,False,False),(30,-45,True,False),(31,-90,False,False),(32,90,True,False),(33,-135,False,False),(34,45,True,False),(35,45,False,False),(36,90,False,False),(37,135,False,False),(38,180,False,False)]:
    base=dirig(angle,both,divider)
    add([NS+str(k)],[base])

cape=dict(Author='Azhou Agent Lab',CapeName='百变阿舟 · 抱一下 3.3.1',CapeVersion=3.31,Cloud=False,HiDPI=True,Identifier='lab.azhou.cursors.doublehug.v331',MinimumVersion=2.,Version=2.,Cursors=roles)

for role, cursor in roles.items():
    count = cursor['FrameCount']
    if count <= 24:
        continue
    indices = [index * count // 24 for index in range(24)]
    duration = cursor['FrameDuration'] * count / 24
    if role == NS + '11':
        duration = .12
    if role in (CG + 'Arrow', CG + 'ArrowS', CG + 'ArrowCtx'):
        indices, duration = [0], 1.0
    representations = []
    for data in cursor['Representations']:
        image = Image.open(io.BytesIO(data)).convert('RGBA')
        edge = image.width
        strip = Image.new('RGBA', (edge, edge * len(indices)))
        for index, selected in enumerate(indices):
            frame = image.crop((0, selected * edge, edge, (selected + 1) * edge))
            strip.paste(frame, (0, index * edge))
        buffer = io.BytesIO()
        strip.save(buffer, 'PNG', optimize=True)
        representations.append(buffer.getvalue())
    cursor.update(FrameCount=len(indices), FrameDuration=duration, Representations=representations)
assert len(roles) == 41
assert all(1 <= cursor['FrameCount'] <= 24 for cursor in roles.values())
out = root / 'Azhou-Double-Hug-3.3.1.cape'
out.write_bytes(plistlib.dumps(cape))
print(f'{out.name}: {len(roles)} cursor states, {out.stat().st_size} bytes')
