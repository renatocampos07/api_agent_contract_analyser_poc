import zipfile
p='backend/data/processed/test_processed_CONTRATO COM MARCA DE COMENTÁRIOS 1.docx'
with zipfile.ZipFile(p,'r') as z:
    s=z.read('word/document.xml').decode('utf-8')
print('len',len(s))
for tag in ['commentRangeStart','commentRangeEnd','commentReference']:
    idx=0
    while True:
        i=s.find(tag,idx)
        if i<0: break
        start=max(0,i-80); end=min(len(s),i+80)
        print('\n---',tag,'at',i)
        print(s[start:end])
        idx=i+len(tag)

# show some context around the first occurrence of 'R$xx,00'
ti = s.lower().find('r$xx,00')
if ti>=0:
    print('\n--- context around R$xx,00:')
    print(s[max(0,ti-200):min(len(s),ti+200)])
else:
    print('\nR$xx,00 not found in document.xml')
