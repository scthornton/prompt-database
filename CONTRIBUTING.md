# Contributing to Prompt Database

Thank you for your interest in contributing to this defensive security research project!

## Code of Conduct

This project is for **defensive security research only**. All contributions must:
- Focus on improving security defenses
- Not enable or encourage malicious use
- Comply with responsible disclosure practices

## How to Contribute

### Reporting Issues
- Use GitHub Issues for bug reports and feature requests
- Provide clear reproduction steps
- Include relevant context and examples

### Contributing Prompts
When adding new attack prompts to the database:

1. **Quality over quantity** - Focus on sophisticated, novel attacks
2. **Categorization** - Properly tag with attack technique and complexity
3. **Documentation** - Explain the attack mechanism and expected behavior
4. **Testing** - Verify the prompt works as described
5. **Attribution** - Credit original sources when applicable

### Contribution Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Make your changes
4. Test thoroughly
5. Commit with clear messages (`git commit -m 'Add: sophisticated context manipulation technique'`)
6. Push to your fork (`git push origin feature/your-feature`)
7. Open a Pull Request

### Commit Message Format

```
Type: Brief description

Longer explanation if needed.

- Bullet points for details
- Reference issues: #123
```

Types: `Add`, `Fix`, `Update`, `Refactor`, `Docs`, `Test`

### Code Style
- Follow PEP 8 for Python code
- Use meaningful variable names
- Add comments for complex logic
- Keep functions focused and testable

### Testing
- Test prompts against multiple models when possible
- Document success rates and model responses
- Report findings responsibly

## Questions?

Open an issue or reach out to the maintainers.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
