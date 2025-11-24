# SQL Lexical Analyzer

---

## 1. Introduction

This report describes the implementation of a lexical analyzer (scanner) for a SQL-like language. The lexer reads SQL code from a file and breaks it down into tokens, which are the basic building blocks that will later be used by a parser.

---

## 2. Tokens Implemented

I implemented several types of tokens to handle different parts of SQL code:

### 2.1 Reserved Keywords (Case-Sensitive)

-   **SQL Commands:** SELECT, FROM, WHERE, INSERT, INTO, VALUES, UPDATE, SET, DELETE, CREATE, TABLE
-   **Data Types:** INT, FLOAT, TEXT
-   **Logical Operators:** AND, OR, NOT

These are stored in a set called `RESERVED_WORDS` and are checked whenever we find an identifier.

### 2.2 Identifiers

-   User-defined names like table names and column names
-   Must start with a letter (a-z or A-Z)
-   Can contain letters, numbers, and underscores
-   Examples: `students`, `user_id`, `firstName`

### 2.3 Literals

-   **String Literals:** Enclosed in single quotes like `'Ali'` or `'Hello World'`
-   **Numeric Literals:**
    -   Integers: `1`, `42`, `1000`
    -   Floats: `3.14`, `0.5`

### 2.4 Operators

-   **Comparison:** `=`, `<`, `>`, `<=`, `>=`, `!=`
-   **Arithmetic:** `+`, `-`, `*`, `/`

### 2.5 Symbols

-   **Parentheses:** `(`, `)`
-   **Comma:** `,`
-   **Semicolon:** `;`
-   **Dot:** `.`

### 2.6 Comments (Skipped)

-   **Single-line:** Starting with `--`
-   **Multi-line:** Enclosed in `##...##`

---

## 3. Error Handling

I implemented three main types of error detection:

### 3.1 Invalid Characters

When the lexer finds a character that doesn't belong to any token type (like `@` or `$`), it reports an error with the line and column number.

**Example:**

```
Input: SELECT @id FROM users;
Error: invalid character '@' at line 1, position 8.
```

**How I did it:** In the main loop, if no token pattern matches, I add an error message with the current position and skip that character.

### 3.2 Unclosed String Literals

If a string starts with `'` but never closes, the lexer detects it and reports where the string started.

**Example:**

```
Input: INSERT INTO test VALUES ('Ali;
Error: unclosed string starting at line 1.
```

**How I did it:** In the `read_string()` function, I keep reading characters until I find the closing quote. If I reach the end of the file without finding it, I report an error.

### 3.3 Unclosed Multi-line Comments

If a comment starts with `##` but doesn't have a closing `##`, the lexer catches this error.

**Example:**

```
Input: SELECT * FROM users; ## this comment never closes
Error: unclosed comment starting at line 1.
```

**How I did it:** In the `skip_multi_line_comment()` function, I search for the closing `##`. If the file ends before finding it, I add an error to the errors list.

---

## 4. Challenges and Solutions

### Challenge 1: Tracking Line and Column Numbers

**Problem:** At first, I had trouble keeping track of where exactly each token was in the file, especially when there were newlines.

**Solution:** I created a special `advance()` function that increments the position, and whenever it sees a newline character (`\n`), it increases the line number and resets the column to 1. For other characters, it just increases the column number.

```python
def advance(self):
    ch = self.source[self.position]
    self.position += 1
    if ch == '\n':
        self.line += 1
        self.column = 1
    else:
        self.column += 1
    return ch
```

### Challenge 2: Distinguishing Between Keywords and Identifiers

**Problem:** Both keywords (like SELECT) and identifiers (like student_name) follow the same pattern - they start with letters and contain letters/numbers. I wasn't sure how to tell them apart.

**Solution:** I created a function `read_identifier_or_keyword()` that first reads the whole word, then checks if it exists in the `RESERVED_WORDS` set. If yes, it's a keyword; if no, it's an identifier. This was really simple and worked well!

### Challenge 3: Handling Two-Character Operators

**Problem:** Some operators are two characters like `<=`, `>=`, `!=`, and `==`. I needed to check ahead before deciding if it's one or two characters.

**Solution:** I made a `peek()` function that lets me look at the next character without moving forward. So I check: if current is `<` and next is `=`, make it `<=`. Otherwise, just make it `<`.

```python
if ch == '<' and self.peek(1) == '=':
    self.advance()
    self.advance()
    return Token('LESS_EQUAL', '<=', start_line, start_column)
```

### Challenge 4: Reading Strings with Special Characters

**Problem:** At first, my string reader would break if there were spaces or special characters inside the quotes.

**Solution:** I changed the loop to accept any character except the closing quote. This way, strings like `'Hello World!'` or `'user@email.com'` work perfectly.

### Challenge 5: Making the Output Look Nice

**Problem:** Initially, the output was just printing Python objects which looked messy and was hard to read.

**Solution:** I created a `print_results()` function that uses Python string formatting to make nice tables with columns for TYPE, LEXEME, LINE, and COLUMN. I used `<` alignment and specified widths like `{token.type:<20}` to make everything line up nicely.

---

## 5. How to Use the Program

1. Save your SQL code in a file (e.g., `input.sql` | `input.txt`).
2. Run the program from terminal:

```bash
python lexer.py input.sql
```

3. The program will show:
    - The source code
    - A table of all tokens
    - A symbol table with identifiers
    - Any errors found

---

## 6. Conclusion

This project helped me understand how compilers work at the first stage. The hardest part was tracking positions and handling errors properly, but once I understood how the `advance()` and `peek()` functions work, everything became much easier.

The lexer successfully identifies all token types, handles comments, and reports errors with exact locations. It's ready to be used as input for a parser in the next stage of building a compiler.

---

## 7. Sample Output

```plain
================================================================================
TOKENS
================================================================================
TYPE                 LEXEME                    LINE       COLUMN
--------------------------------------------------------------------------------
CREATE               CREATE                    1          1
TABLE                TABLE                     1          8
IDENTIFIER           students                  1          14
LEFT_PAREN           (                         1          23
IDENTIFIER           id                        1          24
INT                  INT                       1          27
COMMA                ,                         1          30
IDENTIFIER           name                      1          32
TEXT                 TEXT                      1          37
RIGHT_PAREN          )                         1          41
SEMICOLON            ;                         1          42
================================================================================
```
