# CLAUDE.md - AI Assistant Guide for bot_raid_telegram

## Repository Overview

**Repository Name**: bot_raid_telegram
**Current State**: Early initialization phase
**Project Type**: AL (Application Language) for Dynamics 365 Business Central
**Git Remote**: http://local_proxy@127.0.0.1:28307/git/Wowbrg/bot_raid_telegram

### Repository Status
This repository is in its initial state with minimal files. The project appears to be set up for AL development (Dynamics 365 Business Central extensions) based on the .gitignore configuration.

## Codebase Structure

### Current Files
```
bot_raid_telegram/
├── .git/                 # Git repository data
├── .gitignore           # AL project ignore patterns
└── README.md            # Basic project readme
```

### Expected AL Project Structure
Based on the .gitignore configuration, the following directories/files are expected as the project develops:

- `.vscode/` - VS Code configuration and launch settings
- `.alcache/` - AL cache files (ignored)
- `.alpackages/` - AL package symbols (ignored)
- `.snapshots/` - Snapshot files (ignored)
- `.output/` - Testing output (ignored)
- `*.app` - Compiled extension app files (ignored)
- `rad.json` - Rapid Application Development configuration (ignored)
- `*.g.xlf` - Translation base files (ignored)
- `*.flf` - License files (ignored)
- `TestResults.xml` - Test results (ignored)

## Technology Stack

### AL (Application Language) for Business Central
- **Purpose**: Developing extensions for Microsoft Dynamics 365 Business Central
- **Language**: AL (similar to C/AL but modernized)
- **IDE**: Visual Studio Code with AL Language extension
- **Key Concepts**:
  - Tables, Pages, Reports, Codeunits
  - Events and event subscribers
  - Extensions and customizations
  - Multi-tenancy support

## Development Workflows

### Git Workflow

#### Branch Naming Convention
All development branches MUST follow this pattern:
```
claude/<description>-<session-id>
```

**Current working branch**: `claude/add-claude-documentation-U6Xhn`

#### Important Git Rules
1. **NEVER push to main/master** without explicit permission
2. **ALWAYS develop on designated claude/* branches**
3. **Branch names MUST start with 'claude/'** and end with matching session ID
4. Push will fail with 403 HTTP code if branch naming is incorrect

#### Git Push Protocol
```bash
# Always use -u flag for first push
git push -u origin <branch-name>

# Retry logic for network failures:
# - Retry up to 4 times
# - Exponential backoff: 2s, 4s, 8s, 16s
```

#### Git Fetch/Pull Protocol
```bash
# Prefer fetching specific branches
git fetch origin <branch-name>

# For pulls
git pull origin <branch-name>

# Network failure handling: same retry logic as push
```

### Commit Guidelines

1. **Clear, descriptive messages**: Explain the "why" not just the "what"
2. **Atomic commits**: Each commit should represent one logical change
3. **Follow existing patterns**: Check git log for style consistency
4. **Never commit secrets**: Check .env, credentials.json, etc.

### Pull Request Workflow

When creating a PR:
1. Ensure all changes are committed on the correct branch
2. Push to remote: `git push -u origin <branch-name>`
3. Use `gh pr create` with comprehensive description:
   ```bash
   gh pr create --title "Clear PR title" --body "$(cat <<'EOF'
   ## Summary
   - Bullet point 1
   - Bullet point 2

   ## Test plan
   - [ ] Test item 1
   - [ ] Test item 2
   EOF
   )"
   ```

## Key Conventions for AI Assistants

### File Operations

1. **ALWAYS read before editing**: Never propose changes to code you haven't read
2. **Prefer editing over creating**: Always edit existing files rather than creating new ones
3. **Use specialized tools**:
   - `Read` for reading files (not `cat`)
   - `Edit` for modifying files (not `sed/awk`)
   - `Write` only for new files when absolutely necessary
   - `Glob` for finding files (not `find`)
   - `Grep` for searching content (not `grep/rg`)

### Code Quality Standards

1. **Security First**:
   - No SQL injection vulnerabilities
   - No XSS vulnerabilities
   - No command injection
   - Follow OWASP top 10 guidelines
   - Immediately fix any insecure code discovered

2. **Avoid Over-Engineering**:
   - Only make changes that are directly requested
   - Keep solutions simple and focused
   - Don't add unrequested features or refactoring
   - Don't add comments/docs to unchanged code
   - Don't add error handling for impossible scenarios
   - Don't create abstractions for one-time operations

3. **No Backwards-Compatibility Hacks**:
   - If code is unused, delete it completely
   - No `_unused` variable renaming
   - No `// removed` comments
   - No unnecessary re-exports

### AL-Specific Conventions

When working with AL code:

1. **Naming Conventions**:
   - Objects: PascalCase (e.g., `CustomerCard`, `SalesInvoice`)
   - Variables: camelCase for local, PascalCase for global
   - Follow Business Central naming standards

2. **Object Structure**:
   - Maintain proper object hierarchy
   - Use appropriate object types (Table, Page, Report, Codeunit, etc.)
   - Follow AL extension best practices

3. **Events**:
   - Use event subscribers for extensibility
   - Document event purposes clearly
   - Follow publisher-subscriber pattern

4. **Testing**:
   - Write test codeunits for business logic
   - Use test pages and test methods
   - Maintain test coverage

### Task Management

1. **Use TodoWrite tool** for planning and tracking:
   - Break complex tasks into smaller steps
   - Mark todos in_progress before starting
   - Mark completed immediately after finishing
   - Keep exactly ONE task in_progress at a time

2. **Task States**:
   - `pending`: Not yet started
   - `in_progress`: Currently working on (only one at a time)
   - `completed`: Finished successfully

3. **When to use TodoWrite**:
   - Complex multi-step tasks (3+ steps)
   - Non-trivial tasks requiring planning
   - User provides multiple tasks
   - User explicitly requests todo list

### Communication Style

1. **Concise and technical**: Output is displayed in CLI, be brief
2. **No emojis** unless explicitly requested
3. **Use GitHub-flavored markdown** for formatting
4. **Professional objectivity**: Prioritize accuracy over validation
5. **No timelines**: Provide concrete steps, not time estimates
6. **Code references**: Use `file_path:line_number` format

### Exploration and Research

1. **For open-ended exploration**: Use `Task` tool with `subagent_type=Explore`
2. **For specific files/classes**: Use `Glob` or `Grep` directly
3. **For understanding architecture**: Use exploration agent
4. **Document findings**: Keep notes of discovered patterns

## AL Development Best Practices

### Extension Development

1. **App.json Configuration**:
   - Define proper dependencies
   - Set correct version numbers
   - Specify platform compatibility
   - Include proper publisher information

2. **Object Numbering**:
   - Follow object ID ranges
   - Maintain consistent numbering scheme
   - Document object ID allocation

3. **Permissions**:
   - Define proper permission sets
   - Follow least privilege principle
   - Document permission requirements

4. **Localization**:
   - Use translation files (.xlf)
   - Externalize all user-facing strings
   - Support multi-language scenarios

### Code Organization

1. **Logical Separation**:
   - Separate UI (Pages) from business logic (Codeunits)
   - Keep data model (Tables) clean and focused
   - Use appropriate object types for purpose

2. **Reusability**:
   - Create helper codeunits for common operations
   - Use procedure parameters effectively
   - Avoid code duplication

3. **Documentation**:
   - Add XML documentation to procedures
   - Document complex business logic
   - Explain non-obvious design decisions

## Common Operations

### Starting New Feature Development

```bash
# 1. Ensure you're on the correct branch
git status

# 2. If branch doesn't exist, create it
git checkout -b claude/<feature-name>-<session-id>

# 3. Make changes using appropriate tools
# - Read files first
# - Use Edit for modifications
# - Use Write only for new files

# 4. Commit changes
git add <files>
git commit -m "Clear commit message explaining the why"

# 5. Push to remote
git push -u origin claude/<feature-name>-<session-id>
```

### Code Review Checklist

Before committing AL code, verify:
- [ ] No compilation errors
- [ ] Follows AL naming conventions
- [ ] Security best practices followed
- [ ] No hardcoded values (use setup tables)
- [ ] Error handling is appropriate
- [ ] Code is properly documented
- [ ] Test coverage is adequate
- [ ] No temporary debug code left
- [ ] Translation strings externalized

### Debugging Guidelines

1. **Use AL debugger** in VS Code
2. **Check Event Viewer** for runtime errors
3. **Review telemetry** if available
4. **Test in sandbox** environment first
5. **Validate against Business Central** versions

## Project-Specific Notes

### Current State (as of last update)
- Repository is newly initialized
- No AL code exists yet
- Development environment needs to be set up
- Project scope and requirements to be defined

### Next Steps for Development
1. Set up VS Code with AL Language extension
2. Create app.json with project metadata
3. Define initial object structure
4. Set up development/testing environment
5. Establish coding standards document
6. Create initial extension objects

## Resources and References

### AL Development
- [Microsoft AL Development Documentation](https://docs.microsoft.com/en-us/dynamics365/business-central/dev-itpro/developer/devenv-dev-overview)
- [AL Language Reference](https://docs.microsoft.com/en-us/dynamics365/business-central/dev-itpro/developer/devenv-reference-overview)
- [Best Practices for AL](https://docs.microsoft.com/en-us/dynamics365/business-central/dev-itpro/developer/devenv-dev-best-practices)

### Git Workflow
- Feature branches follow `claude/*` pattern
- Always push with `-u origin <branch-name>`
- Network retries: 4 attempts with exponential backoff

### Support
- For git issues: Check branch naming and network connectivity
- For AL issues: Refer to official Business Central documentation
- For development questions: Use exploration tools to understand existing code

---

**Last Updated**: 2026-01-05
**Document Version**: 1.0
**Maintained By**: AI Assistant (Claude)
