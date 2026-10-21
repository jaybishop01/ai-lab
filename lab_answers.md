# Answers: Make your data AI ready with dbt and Snowflake

The escape hatch. Try the hints on the slides first. Come here when you're stuck or want to check your work.

## Part 1: Explore the catalog {#part-1-catalog}

**Done when:** you can trace the semantic view back to raw data and say which signals decide a student's risk.

**The lineage.** `HED_RECORDS` (source) → `stg_hed__students` → `int_hed__risk_levels` → `vw_hed_retention_risk_analysis` → `sv_hed_at_risk_students` (semantic view).

**The risk score.** `int_hed__risk_levels` scores four signals: GPA, course completion, engagement, and login recency. Overall risk is the worst of the four. If any one is Critical, the student is Critical. So a student with a 3.9 GPA who hasn't logged in for 15+ days is still Critical.

**What's tested.** `stg_hed__students`, the intermediate models, and the marts have tests. The four `dq_hed__*` models and the semantic view model have none. That's your target for the Wizard step.

**Stretch.** In column-level lineage, `OVERALL_RISK_ASSESSMENT` traces back to `CURRENT_GPA`, `COURSE_COMPLETION_RATE`, `ENGAGEMENT_SCORE`, and `LAST_LOGIN_DATE` in `HED_RECORDS`.

## Part 1: dbt Wizard {#part-1-wizard}

**Done when:** you can explain the project in 2-3 sentences, one model has a new description, at least 2 new tests pass, and `dbt build` is green.

**The project in 3 sentences.** Raw student records land in `HED_RECORDS` (synced by Fivetran). `stg_hed__students` cleans them; two intermediate models score risk and engagement; five marts serve KPIs, retention risk, engagement, program performance, and data quality. `sv_hed_at_risk_students` turns the retention mart into a Snowflake semantic view that Cortex Analyst can query.

**Where the gaps are.** The four `dq_hed__*` models have no tests. The `sv_hed_at_risk_students` model has no description.

**Example tests.** In `models/hed/data_quality/_data_quality__schema.yml`, find `dq_hed__validity`. Its columns are already listed with descriptions. Add a `data_tests:` block under `quality_dimension` and `overall_validity_score`, so they look like this:

```yaml
      - name: quality_dimension
        description: "Quality dimension identifier (Data Validity)"
        data_tests:
          - not_null
          - accepted_values:
              values: ['Data Validity']
      - name: overall_validity_score
        description: "..."   # keep the existing description
        data_tests:
          - not_null
```

**Example description.** Create `models/hed/semantic_models/_semantic_models.yml`:

```yaml
version: 2
models:
  - name: sv_hed_at_risk_students
    description: >
      Snowflake semantic view over vw_hed_retention_risk_analysis. Gives Cortex Analyst
      the facts, dimensions, and filters it needs to answer plain-English questions
      about at-risk students.
```

Then run `dbt build --select data_quality sv_hed_at_risk_students`.

**Stretch.** A test that fails when data goes bad: `invalid_gpa_records` should always be 0. Add this under the existing `invalid_gpa_records` column:

```yaml
      - name: invalid_gpa_records
        data_tests:
          - dbt_utils.accepted_range:
              min_value: 0
              max_value: 0
```

## Part 2: Custom agent function {#part-2-function}

`ROUTE_STUDENT_ALERT` takes a student ID and returns that student's risk details plus who to notify: the Dean, the Department Chair, or the Advisor.

```sql
CREATE OR REPLACE FUNCTION sv_higher_education.ROUTE_STUDENT_ALERT("STUDENT_ID_INPUT" VARCHAR)
RETURNS OBJECT
LANGUAGE SQL
COMMENT='Prepares a student retention alert payload for routing to academic staff. Returns student risk data with routing recommendation based on severity. Used by Cortex Agent for alert activation.'
AS '
SELECT OBJECT_CONSTRUCT(
    -- Student identification
    ''student_id'', s.STUDENT_ID,
    ''major_code'', s.MAJOR_CODE,
    ''advisor_id'', s.ADVISOR_ID,
    ''academic_standing'', s.ACADEMIC_STANDING,

    -- Risk assessment
    ''overall_risk_assessment'', s.OVERALL_RISK_ASSESSMENT,
    ''at_risk_flag'', s.AT_RISK_FLAG,

    -- Academic metrics
    ''current_gpa'', s.CURRENT_GPA,
    ''gpa_risk_level'', s.GPA_RISK_LEVEL,
    ''course_completion_rate'', s.COURSE_COMPLETION_RATE,
    ''completion_risk_level'', s.COMPLETION_RISK_LEVEL,

    -- Engagement metrics
    ''engagement_score'', s.ENGAGEMENT_SCORE,
    ''engagement_risk_level'', s.ENGAGEMENT_RISK_LEVEL,
    ''days_since_last_login'', s.DAYS_SINCE_LAST_LOGIN,
    ''login_recency_risk_level'', s.LOGIN_RECENCY_RISK_LEVEL,

    -- Activity metrics
    ''total_course_views'', s.TOTAL_COURSE_VIEWS,
    ''assignment_submissions'', s.ASSIGNMENT_SUBMISSIONS,
    ''discussion_posts'', s.DISCUSSION_POSTS,

    -- Financial & intervention
    ''financial_aid_amount'', s.FINANCIAL_AID_AMOUNT,
    ''financial_aid_category'', s.FINANCIAL_AID_CATEGORY,
    ''intervention_count'', s.INTERVENTION_COUNT,
    ''intervention_category'', s.INTERVENTION_CATEGORY,
    ''plagiarism_incidents'', s.PLAGIARISM_INCIDENTS,
    ''writing_quality_score'', s.WRITING_QUALITY_SCORE,

    -- Pre-generated recommendations
    ''recommended_action'', s.RECOMMENDED_ACTION,

    -- ROUTING DECISION LOGIC
    ''routing_recommendation'',
        CASE
            WHEN s.OVERALL_RISK_ASSESSMENT LIKE ''%Critical%'' THEN ''NOTIFY_DEAN''
            WHEN s.CURRENT_GPA < 2.0 THEN ''NOTIFY_DEAN''
            WHEN (s.GPA_RISK_LEVEL = ''Critical'' AND s.COMPLETION_RISK_LEVEL = ''Critical'') THEN ''NOTIFY_DEAN''
            WHEN (s.GPA_RISK_LEVEL = ''Critical'' AND s.ENGAGEMENT_RISK_LEVEL = ''Critical'') THEN ''NOTIFY_DEAN''
            WHEN s.OVERALL_RISK_ASSESSMENT LIKE ''%High%'' THEN ''NOTIFY_DEPT_CHAIR''
            WHEN s.GPA_RISK_LEVEL = ''Critical'' OR s.COMPLETION_RISK_LEVEL = ''Critical'' THEN ''NOTIFY_DEPT_CHAIR''
            WHEN s.ENGAGEMENT_RISK_LEVEL = ''Critical'' OR s.LOGIN_RECENCY_RISK_LEVEL = ''Critical'' THEN ''NOTIFY_DEPT_CHAIR''
            WHEN s.DAYS_SINCE_LAST_LOGIN > 21 THEN ''NOTIFY_DEPT_CHAIR''
            WHEN s.ACADEMIC_STANDING IN (''Probationary Status'', ''Academic Probation'', ''Academic Warning'', ''Warning Status'') THEN ''NOTIFY_DEPT_CHAIR''
            ELSE ''NOTIFY_ADVISOR''
        END,

    ''escalation_minutes'',
        CASE
            WHEN s.OVERALL_RISK_ASSESSMENT LIKE ''%Critical%'' OR s.CURRENT_GPA < 2.0 THEN 10
            WHEN s.OVERALL_RISK_ASSESSMENT LIKE ''%High%'' OR s.GPA_RISK_LEVEL = ''Critical'' THEN 15
            ELSE 30
        END,

    ''priority_level'',
        CASE
            WHEN s.OVERALL_RISK_ASSESSMENT LIKE ''%Critical%'' OR s.CURRENT_GPA < 2.0 THEN ''Critical''
            WHEN s.OVERALL_RISK_ASSESSMENT LIKE ''%High%'' OR s.GPA_RISK_LEVEL = ''Critical'' THEN ''High''
            ELSE ''Medium''
        END,

    ''alert_timestamp'', CURRENT_TIMESTAMP(),
    ''alert_date'', TO_CHAR(CURRENT_DATE(), ''YYYY-MM-DD''),
    ''status'', ''ALERT_READY''
)
FROM sv_higher_education.vw_hed_retention_risk_analysis s
WHERE s.STUDENT_ID = student_id_input
';
```

Test it:

```sql
SELECT sv_higher_education.ROUTE_STUDENT_ALERT('STU_202400421');  -- routing_recommendation: NOTIFY_DEAN
SELECT sv_higher_education.ROUTE_STUDENT_ALERT('STU_202400015');  -- NOTIFY_DEPT_CHAIR
SELECT sv_higher_education.ROUTE_STUDENT_ALERT('STU_202400075');  -- NOTIFY_ADVISOR
```

## Part 2: Create the agent {#part-2-agent}

In Snowsight: **AI & ML → Agents → + Agent**.

When it asks where to create the agent, pick your lab database and the `SV_HIGHER_EDUCATION` schema.

| Field | Value |
|---|---|
| Agent name | `RIDGELINE_STUDENT_SUCCESS_AGENT` |
| Display name | `Ridgeline Student Success Agent` |
| Available in Snowflake Intelligence | On |

**Description**
```
Student retention agent for Ridgeline State's Student Success office. Answers plain-English questions about at-risk students and routes alerts to the Dean, Department Chair, or Advisor. Built on data modeled with dbt.
```

**Orchestration instructions**
```
You are a Student Retention agent that helps academic staff identify and respond to at-risk students.

TOOL SELECTION:
1. For questions about student data, risk scores, academic performance, or statistics -> use query_student_risk_data (Cortex Analyst)
2. For routing an alert for a specific student -> use route_student_alert (requires student_id)

REASONING PROCESS:
1. Understand if the user wants information (query) or action (alert)
2. For queries: use query_student_risk_data to search student retention data
3. For alerts: get the student_id first (ask if not provided), then use route_student_alert

IMPORTANT:
- Overall risk assessment values: Critical, High, Moderate, Low
- GPA below 2.0 is the critical threshold
- 21+ days inactive requires immediate intervention
- Critical risk -> routed to Dean (10-min escalation)
- High risk -> routed to Department Chair (15-min escalation)
- Moderate or Low risk -> routed to Academic Advisor (30-min escalation)
- Always include student_id, major, advisor, and risk assessment when discussing students
```

**Response instructions**
```
Tone: Professional and supportive, but urgent when discussing critical-risk students.

Format:
- Lead with the most important information (risk level, student count, priority)
- Include specific numbers (GPA, engagement scores, counts)
- For student details: always show Student ID, Major, Risk Assessment, GPA, Advisor

Alert responses - when routing an alert, confirm:
- Student ID and major
- Routing destination (Dean, Department Chair, or Academic Advisor)
- Key risk factors triggering the alert
- Say the alert is prepared for that person, not sent. This tool doesn't send anything.

Never:
- Skip confirming student_id before routing alerts
- Provide academic or counseling advice beyond the data
- Ignore critical risk indicators
```

**Tool 1: Cortex Analyst**

| Field | Value |
|---|---|
| Tool name | `query_student_risk_data` |
| Database | your lab database |
| Schema | `SV_HIGHER_EDUCATION` |
| Semantic view | `SV_HED_AT_RISK_STUDENTS` |
| Warehouse | the warehouse your worksheet uses |

```
Query student retention data, risk scores, academic performance, and statistics using natural language. Use this tool to answer questions about at-risk students, filter by major or risk level, calculate aggregate metrics, or analyze retention trends.
```

**Tool 2: Function**

| Field | Value |
|---|---|
| Tool name | `route_student_alert` |
| Resource type | `function` |
| Function | `<your lab database>.SV_HIGHER_EDUCATION.ROUTE_STUDENT_ALERT(VARCHAR)` |
| Warehouse | the warehouse your worksheet uses |

The form lists one parameter, `STUDENT_ID_INPUT`. Give it this description: `Student ID, e.g. STU_202400421`

```
Use this tool to route a retention alert for a specific student. Requires a student_id (e.g., STU_202400421). Returns the student's details, risk assessment, recommended actions, and routing destination (NOTIFY_DEAN, NOTIFY_DEPT_CHAIR, or NOTIFY_ADVISOR). Use when the user asks to route an alert, send an alert, or notify someone about a specific student.
```

**Example questions**
```
Which students have critical retention risk right now?
Show me the top 10 highest risk students
Find Engineering students with low GPA
What's the average engagement score by major?
Which students are inactive for more than 21 days?
Summarize STU_202400421's risk factors
How many students are on academic probation?
Route an alert for STU_202400421
What's the total financial aid at risk for critical students?
Which majors have the most critical-risk students?
```

Click **Create**.

## Part 2: Test set with known answers {#part-2-tests}

Check your agent against these. Answers come from the lab data, so they're the same for everyone.

| Question | Known answer |
|---|---|
| How many students are at Critical risk? | 132 |
| How many students are at High risk? | 95 |
| How many students haven't logged in for more than 21 days? | 12 |
| How many students are on probation or warning? | 77 |
| Total financial aid for Critical-risk students? | about $1.63M ($1,627,934) |
| Which majors have the most Critical-risk students? | JOUR and NURS, 8 each |
| Route an alert for STU_202400421 | Dean (Critical, GPA 1.01) |
| Route an alert for STU_202400015 | Department Chair |
| Route an alert for STU_202400075 | Advisor |

**Found a wrong answer?** Common fixes: add the term to the semantic view's synonyms or descriptions, add a rule to the orchestration instructions, or add a verified query. Change one thing, then ask again.
