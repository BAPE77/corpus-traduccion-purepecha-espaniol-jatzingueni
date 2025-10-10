import re

def segmentSentences(paragraphs):
    sentences = []
    sentencePattern = re.compile(r'[.!?\d¿]+\s+')
    
    for p in paragraphs:
        parts = sentencePattern.split(p)
        for part in parts:
            part = part.strip()
            if part: #and len(part) > 3 and re.match(r'^[a-zA-Z]+', part):
                sentences.append(part)
    
    return sentences

symbolTimes = 90
print("=="*symbolTimes)
sentences = segmentSentences(["5 Veamos lo que podemos aprender del ejemplo del rey David, que fue humilde a pesar de sus logros y habilidades. Muchos años antes de ser rey, ya era un músico famoso, y hasta tocaba delante del rey Saúl (1 Sam. 16:18, 19). Cuando Jehová lo eligió para que fuera el siguiente rey, lo llenó de poder con su espíritu santo (1 Sam. 16:11-13). Y el pueblo lo aclamaba porque había derrotado a muchísimos enemigos, como Goliat, el gigante filisteo (1 Sam. 17:37, 50; 18:7). Si hubiera sido orgulloso, David podría haber pensado: “Con todo lo que he logrado en mi vida, no necesito que nadie me dé consejos”. Pero él no era así. 6. ¿Cómo sabemos que David aceptaba con gusto que le dieran consejos? (Vea también la imagen)."])
for sentence in sentences:
    print(sentence)
print(len(sentences))
print("=="*symbolTimes)
sentences = segmentSentences(["5 Iásï, ju je exeni ambechi uaa jorhenguarhini rei Dabidiiri ambe. Ima kaxumbitiispti nájkiruka uánikua ambe úpkia ka mámaru ambe jorhenani úni. Ante de reini, ima kánikua sési kústasïreendi ka asta kústakusïreendi rei Saúlini (1 Sam. 16:18, 19). Ísï jimbo, enga Tata Diosï Jeoba erakupka paraka reipiringa, íntskuspti uinhapikua imeeri espiritu santu jimbo (1 Sam. 16:11-13). Ka enga ireta exeenga Dabidini, k’éri ambe arhisïreendi jimboka ima uándikuspka Goliatini, achamasïni ma enga kánikua iójtarhapka ka Filistea anapueni (1 Sam. 17:37, 50; 18:7). Joperu Dabidi no méni kʼéramakuarhispti nijtu eratsepi: “No uétarhinchasïnga eskarini nema konseju íntskuaka jimbokani uánikua ambe úskia”. 6. ¿Nénachi míteski eska Dabidi jiókuarhiasïreenga imani konsejuechani enga intsïnhauenga? (Ístu exe je imajenini)."])
for sentence in sentences:
    print(sentence)
print(len(sentences))
print("=="*symbolTimes)