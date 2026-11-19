import struct,sys
f=open(sys.argv[1],'rb')
f.seek(4096); g=f.read(4096)
magic,sz=struct.unpack('<II',g[:8]); assert magic==0x616c4467,hex(magic)
msz,mslots,lbs=struct.unpack('<III',g[40:52])
base=4096+4096*2  # primary metadata
f.seek(base); h=f.read(msz)
assert struct.unpack('<I',h[:4])[0]==0x414C5030
hsz=struct.unpack('<I',h[8:12])[0] if False else struct.unpack('<I',h[8:12])[0]
hsz=struct.unpack('<I',h[8:12])[0]
# header: magic,major,minor,header_size,header_checksum[32],tables_size,tables_checksum[32],partitions desc,extents desc,groups,block_devices
maj,minr,hsz=struct.unpack('<HHI',h[4:12])
off=12+32
tsz=struct.unpack('<I',h[off:off+4])[0]; off+=4+32
descs=[struct.unpack('<III',h[off+i*12:off+i*12+12]) for i in range(4)]
T=h[hsz:hsz+tsz]
po,pn,pes=descs[0]; eo,en,ees=descs[1]
ext=[struct.unpack('<QIQI',T[eo+i*ees:eo+i*ees+24]) for i in range(en)]
for i in range(pn):
    p=T[po+i*pes:po+(i+1)*pes]
    name=p[:36].rstrip(b'\0').decode(); attr,fi,ne,grp=struct.unpack('<IIII',p[36:52])
    for e in ext[fi:fi+ne]:
        print(name,e[0]*512,e[2]*512,e[1])
