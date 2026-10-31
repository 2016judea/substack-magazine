import glob,os,sys
from PIL import Image
D=os.path.dirname(os.path.abspath(__file__))+'/qa'
fs=sorted(glob.glob(D+'/pages/p*.png'));os.makedirs(D+'/pairs',exist_ok=True)
for f in glob.glob(D+'/pairs/*.png'): os.remove(f)
for k in range(0,len(fs),2):
    ims=[Image.open(f) for f in fs[k:k+2]];ims=[i.resize((560,int(i.height*560/i.width))) for i in ims]
    o=Image.new('RGB',(1130,ims[0].height),'#888');x=0
    for i in ims:o.paste(i,(x,0));x+=570
    o.save(D+'/pairs/'+os.path.basename(fs[k]))
print(len(fs))
