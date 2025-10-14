import re

def segmentSentences(paragraphs):
    bibleRefPattern = re.compile(r'\([^\)]*\d+[:]\d+[^\)]*\)')
    leadingNumberPattern = re.compile(r'^\s*\d+\s*')
    enumMarker = re.compile(
        r'(?:(?<=^)|(?<=\s)|(?<=:)|(?<=,))\s*(?:y|ka)?\s*(\d+|[a-zA-Z])[.)]\s*(?:["“]?\s*¿?)',
        re.IGNORECASE
    )
    sentences = []

    for paragraph in paragraphs:
        text = paragraph.strip()
        text = bibleRefPattern.sub('', text)
        text = leadingNumberPattern.sub('', text)
        text = text.replace('“', '"').replace('”', '"').replace('‘', "'").replace('’', "'")
        marked = enumMarker.sub('|||ENUM|||', text)
        rawParts = [p.strip() for p in marked.split('|||ENUM|||') if p.strip()]

        sentencePattern = re.compile(r'(.*?)([.!?]+(?:["\)\]\}]*)?(?:[,;:]*\s+|$))', re.S)

        for part in rawParts:
            subparts = []
            i = 0
            for m in sentencePattern.finditer(part):
                piece = (m.group(1) + m.group(2)).strip()
                if piece:
                    subparts.append(piece)
                i = m.end()
            if i < len(part):
                leftover = part[i:].strip()
                if leftover:
                    subparts.append(leftover)
            if not subparts:
                subparts = [part]
            for sp in subparts:
                sp = sp.strip()
                sp = re.sub(r'\s+([?.!,;:])', r'\1', sp)
                sp = sp.strip(' \'"()[]{}')
                if sp.startswith('¿') or sp.startswith('¡'):
                    sp = sp[1:].lstrip()
                sp = enumMarker.sub('', sp).strip()
                sp = sp.replace('"', '').replace("'", '').strip()
                sp = re.sub(r'\s+([?.!])', r'\1', sp)
                sp = re.sub(r'^[^A-ZÁÉÍÓÚÑÄËÏÖÜ]+', '', sp)
                sp = re.sub(r'\s+', ' ', sp)
                if sp and len(sp) > 1:
                    sentences.append(sp)
    return sentences

symbolTimes = 90
print("=="*symbolTimes)
sentences = segmentSentences(["4 Parajtsïni marhuacheni konseju ma, jatsiskachi para kaxumbitiini  ka jiókuarhini eskachi no iámindu ambe míteska. Ísï jimbo, parajtsïni sési uérachini ambe ma, jatsiskachi para imani kʼuiripueni kurhakuni konseju ma enga sánderu ambe míteka eska jucha. Engachi no xarhatauaka indeni kualidadiichani Tata Diosï Jeobajtsïni no uaati jarhuatani ka sánderu úkua jukaati ísï úni eskaksï Biblieri konsejuecha na uandajka (Miq. 6:8; 1 Ped. 5:5). Joperu engachi kaxumbitiiska, sánderuchi jingontku jauaka parachi ísï úni eska Biblia na uandajka."])
for sentence in sentences:
    print(sentence)
print(len(sentences))
print("=="*symbolTimes)
sentences = segmentSentences(["4 Para beneficiarnos de los buenos consejos que recibamos, tenemos que ser humildes y modestos. Debemos admitir que a menudo tomaremos mejores decisiones si le pedimos consejo a alguien que tenga más experiencia o sepa más que nosotros. Sin estas cualidades, Jehová no podrá ayudarnos y, entonces, no veremos la necesidad de aplicar los consejos que leamos en su Palabra (Miq. 6:8; 1 Ped. 5:5). Pero, si somos humildes, tendremos los  oídos abiertos a cualquier consejo que venga de la Biblia."])
for sentence in sentences:
    print(sentence)
print(len(sentences))
print("=="*symbolTimes)