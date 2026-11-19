import sys,zipfile
from loguru import logger; logger.remove()
from androguard.core.axml import AXMLPrinter
for p in sys.argv[1:]:
    try:
        x=AXMLPrinter(zipfile.ZipFile(p).read('AndroidManifest.xml')).get_xml_obj()
        print(x.get('package'), p)
    except Exception as e: print('ERR',p,e)
