# md2markup

Markdown을 Confluence Wiki Markup으로 변환하는 CLI 툴.

구버전 Confluence는 Markdown을 지원하지 않습니다. `md2markup input.md` 한 줄로 `.txt` 파일(Confluence Wiki Markup)을 생성합니다.

- 외부 의존성 없음 (Python 표준 라이브러리만 사용)
- Python 3.8+

---

## 설치

### 방법 1: 스크립트 직접 사용

별도 설치 없이 `md2markup.py`를 바로 실행합니다.

```bash
# Windows
python md2markup.py input.md

# macOS / Linux
python3 md2markup.py input.md

# macOS / Linux — 직접 실행 (chmod 한 번만 필요)
chmod +x md2markup.py
./md2markup.py input.md
```

### 방법 2: pip install (전역 명령어로 사용)

```bash
pip install .
```

설치 후 어디서든 `md2markup` 명령어를 사용할 수 있습니다.

> **참고**: 환경에 따라 `pip` 대신 `pip3`를 사용해야 할 수 있습니다.

---

## 사용법

```
md2markup <input.md> [-o output.txt] [--stdout]
```

| 옵션 | 설명 |
|---|---|
| `input.md` | 변환할 Markdown 파일 (필수) |
| `-o output.txt` | 출력 파일 경로 지정 (기본값: 입력 파일과 같은 이름, `.txt` 확장자) |
| `--stdout` | 파일 저장 없이 터미널에 출력 |

### 예시

```bash
# input.md → input.txt 로 저장
md2markup input.md

# 출력 파일 이름 직접 지정
md2markup input.md -o result.txt

# 터미널에 바로 출력
md2markup input.md --stdout

# 파이프로 활용
md2markup input.md --stdout | clip   # Windows 클립보드로 복사
md2markup input.md --stdout | pbcopy # macOS 클립보드로 복사
```

---

## 변환 규칙

| Markdown | Confluence Wiki Markup |
|---|---|
| `# H1` ~ `###### H6` | `h1. H1` ~ `h6. H6` |
| `**bold**` / `__bold__` | `*bold*` |
| `*italic*` / `_italic_` | `_italic_` |
| `***bold italic***` | `*_bold italic_*` |
| `~~strike~~` | `-strike-` |
| `` `code` `` | `{{code}}` |
| `` `{ "json": ... }` `` (중괄호 포함) | `{{&#123;"json": ...&#125;}}` (HTML 엔티티 이스케이프) |
| ` ```lang\ncode\n``` ` | `{code:language=lang}\ncode\n{code}` |
| `- item` / `* item` | `* item` |
| `1. item` | `# item` |
| 중첩 리스트 (들여쓰기 2칸) | `**`, `##`, `*#` 등 depth별 기호 |
| `- [ ] task` | `* ( ) task` |
| `- [x] task` | `* (/) task` |
| `> quote` | `bq. quote` |
| `---` / `***` (단독 라인) | `----` |
| `[text](url)` | `[text\|url]` |
| `![alt](url)` | `!url!` |
| 테이블 헤더 행 | `\|\|cell\|\|cell\|\|` |
| 테이블 데이터 행 | `\|cell\|cell\|` |

> **참고**: 인라인 코드(`` `...` ``)에 `{` 또는 `}`가 포함된 경우, Confluence가 `{{...}}`를 매크로로 파싱해 "Unknown macro" 오류가 발생합니다. 이 경우 중괄호를 HTML 엔티티(`&#123;` / `&#125;`)로 자동 이스케이프하여 `{{...}}` 형식을 유지합니다. 테이블 셀 안에서도 올바르게 렌더링됩니다.

---

## 알려진 제한사항

- **중첩 블록쿼트** (`>> ...`) → 단일 `bq.`로 평탄화 (Confluence 미지원)
- **느슨한 리스트** (항목 사이 빈 줄) → 리스트 재시작으로 처리
- **HTML 태그** → 변환 없이 그대로 통과

---

## 개발 / 테스트

```bash
# unittest (pytest 없이)
python -m unittest discover tests/ -v

# pytest 사용 시
pytest tests/ -v
```
