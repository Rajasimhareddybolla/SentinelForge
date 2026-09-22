# Pull request review instructions

When reviewing pull requests, check:

## Code quality
- Readability and maintainability
- Clear naming
- Duplicate or unnecessarily complex code
- Error handling
- Tests for new behavior
- Backward compatibility
- Performance regressions

## Security
- Authentication and authorization
- Input validation
- Injection vulnerabilities
- Sensitive information and secrets
- Unsafe file or command execution
- Insecure dependencies
- Improper logging of private data

## Review behavior
- Report only actionable findings.
- Explain why each finding matters.
- Include the affected file and line.
- Suggest a specific fix.
- Do not request changes for formatting if the formatter already handles them.
- Treat security issues as high priority.