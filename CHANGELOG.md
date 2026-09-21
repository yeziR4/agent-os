# Changelog

All notable changes to AgentOS will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Fixed
- Telegram channel: a backslash-escaped Markdown character (`` \* ``, `` \_ ``
  or `` \` ``) was printed to the user *and* still triggered the formatting
  it was meant to suppress -- worst of all, an escaped backtick still opened
  a real `<code>` span, landing the stray backslash inside it.
  `_replace_code_spans` and `_plain_inline` now consume a CommonMark
  backslash escape before any code-span or emphasis pass can see the escaped
  character (#3305).

## [2026.9.22] - 2026-09-22

### Fixed
