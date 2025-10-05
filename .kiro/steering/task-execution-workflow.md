# Task Execution Workflow - SEC Climate Disclosure API

## 🎯 **Task Execution Protocol**

When executing tasks from `.kiro/specs/sec-climate-disclosure-api/tasks.md`, follow this systematic approach:

### 📋 **Pre-Task Checklist**

1. **Read Spec Documents**:

   - `requirements.md` - Understand feature requirements
   - `design.md` - Review technical design
   - `tasks.md` - Check task details and dependencies

2. **Check Current Status**:
   - Review completed tasks
   - Identify dependencies
   - Understand current codebase state

### 🔄 **Task Execution Steps**

1. **Start Task**:

   - Update task status to "in_progress"
   - Focus on ONE task at a time
   - Don't auto-proceed to next task

2. **Implementation**:

   - Follow service-layer-first approach
   - Write tests for core functionality
   - Implement business logic before API endpoints

3. **Database Changes**:

   - If models change → Create migration
   - Run `alembic upgrade head`
   - Verify with tests

4. **Testing**:

   - Run relevant tests
   - Fix any failures
   - Ensure functionality works as expected

5. **Complete Task**:
   - Update task status to "completed"
   - Stop and wait for user review
   - Don't automatically continue to next task

### 🚨 **Critical Rules**

- **ONE TASK AT A TIME** - Never implement multiple tasks simultaneously
- **STOP AFTER COMPLETION** - Always wait for user review before next task
- **DATABASE FIRST** - Migrate schema changes immediately
- **TEST EVERYTHING** - Verify functionality works correctly
- **SERVICE LAYER FIRST** - Implement business logic before API endpoints

### 📊 **Task Categories**

**Core Services** (6.x):

- Focus on business logic and data processing
- Require comprehensive testing
- May need database schema updates

**API Endpoints** (7.x):

- Build on existing services
- Focus on request/response handling
- Require API testing

**Validation & Quality** (8.x):

- Data validation and quality scoring
- Error handling and edge cases
- Performance considerations

**Export & Reporting** (9.x):

- Data transformation and formatting
- File generation and delivery
- Integration with external systems

### ✅ **Success Criteria**

- Task functionality works as specified
- All tests pass
- Database schema is up-to-date
- Code follows project patterns
- No breaking changes to existing functionality

This workflow ensures systematic, reliable task execution with proper database management and testing.
