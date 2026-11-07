# usage: mkb2.py out.bin name bdf.bin  -> ath11k board-2.bin with one board entry
import sys,struct
def ie(t,v):
    pad=(4-len(v)%4)%4
    return struct.pack('<II',t,len(v))+v+b'\0'*pad
out,name,bdf=sys.argv[1:4]
magic=b'QCA-ATH11K-BOARD\0'; magic+=b'\0'*((4-len(magic)%4)%4)
board=ie(0,name.encode())+ie(1,open(bdf,'rb').read())
open(out,'wb').write(magic+ie(0,board))
