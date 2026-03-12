import textwrap, ast

with open('/app/8_app.py') as f:
    lines = f.readlines()

start, end = 303, 704

# Corps = sauter "if st.session_state.selected:" et "r = st.session_state.selected"
body = lines[start+2:end]

# Soustraire exactement 8 espaces (indentation minimale du bloc)
def dedent_n(lines, n):
    result = []
    for l in lines:
        if l.startswith(' ' * n):
            result.append(l[n:])
        elif l.strip() == '':
            result.append('\n')
        else:
            result.append(l)
    return result

body_dedented = dedent_n(body, 8)

# Ajouter 4 espaces (indentation dans def show_fiche)
body_indented = []
for l in body_dedented:
    if l.strip():
        body_indented.append('    ' + l)
    else:
        body_indented.append('\n')

dialog_func = (
    ['# ── Fiche detail dialog ─────────────────────────────────────────────────────\n',
     '@st.dialog("Fiche detail", width="large")\n',
     'def show_fiche(r):\n',
     '    title_q     = str(r.get("title",""))\n',
     '    author_q    = str(r.get("author",""))\n',
     '    title_slug  = title_q.replace(" ","+")\n',
     '    author_slug = author_q.replace(" ","+")\n',
    ]
    + body_indented
    + ['\n\n']
)

call = [
    '    if st.session_state.selected:\n',
    '        show_fiche(st.session_state.selected)\n',
]

new_lines = lines[:start] + call + lines[end:]
insert_at = next(i for i,l in enumerate(new_lines) if 'if page ==' in l and 'Catalogue' in l)
new_lines = new_lines[:insert_at] + dialog_func + new_lines[insert_at:]

with open('/app/8_app.py', 'w') as f:
    f.writelines(new_lines)

try:
    ast.parse(''.join(new_lines))
    print('OK syntaxe')
except SyntaxError as e:
    print(f'ERREUR ligne {e.lineno}: {e.msg}')
    for i in range(max(0,e.lineno-4), min(len(new_lines), e.lineno+3)):
        print(f'{i+1:4d} {repr(new_lines[i])}')
