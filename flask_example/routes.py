import random
import string

from flask import render_template, redirect, url_for, flash, request, Response
from flask_example import app
from flask_example.forms import BudgetingForm
from flask_example import lottery_wrapper as lw


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Fixed list of project and voter names used when generating random input
_PROJECT_NAMES = [
    'Park', 'Library', 'Roads', 'School', 'Hospital', 'Bridge',
    'Playground', 'Museum', 'Sports_Center', 'Community_Hall',
]
_VOTER_NAMES = [
    'Alice', 'Bob', 'Carol', 'Dave', 'Eve', 'Frank',
    'Grace', 'Hank', 'Iris', 'Jack', 'Karen', 'Leo',
    'Mia', 'Ned', 'Olivia', 'Pat', 'Quinn', 'Ray',
    'Sara', 'Tom',
]

# GCR runtime grows exponentially with number of projects/voters — cap both
GCR_MAX_PROJECTS = 10
GCR_MAX_VOTERS   = 20


def _generate_random_input(n_voters, n_projects):
    """
    Return (budget_str, projects_text, preferences_text, warnings) with random data.
    warnings is a list of (message, category) tuples to flash.
    """
    warnings = []

    # Pick project names — extend with generic names if more than the fixed list
    if n_projects <= len(_PROJECT_NAMES):
        projects = random.sample(_PROJECT_NAMES, n_projects)
    else:
        projects = list(_PROJECT_NAMES) + [
            f'Project_{i}' for i in range(1, n_projects - len(_PROJECT_NAMES) + 1)
        ]

    # Pick voter names — extend with generic names if more than the fixed list
    if n_voters <= len(_VOTER_NAMES):
        voters = random.sample(_VOTER_NAMES, n_voters)
    else:
        extra = [f'Voter_{i}' for i in range(1, n_voters - len(_VOTER_NAMES) + 1)]
        voters = list(_VOTER_NAMES) + extra

    # Warn if GCR limits will be applied when the algorithm runs
    if n_projects > GCR_MAX_PROJECTS:
        warnings.append((
            f'Note: BW-GCR-PB will run with only {GCR_MAX_PROJECTS} of the {n_projects} projects.',
            'info'
        ))
    if n_voters > GCR_MAX_VOTERS:
        warnings.append((
            f'Note: BW-GCR-PB will run with only {GCR_MAX_VOTERS} of the {n_voters} voters.',
            'info'
        ))

    # Generate random costs and a budget that allows funding some (but not all) projects
    base_cost = random.randint(3, 12) * 1000
    costs = {p: random.randint(1, 5) * base_cost for p in projects}
    total_cost = sum(costs.values())
    budget = random.randint(
        max(min(costs.values()), total_cost // (n_projects + 1)),
        max(total_cost * 2 // 3, min(costs.values()) * 2)
    )

    # Format projects as "Name: cost" lines for the textarea
    projects_text = '\n'.join(f'{p}: {c}' for p, c in costs.items())

    # Each voter approves a random non-empty subset of projects
    pref_lines = []
    for v in voters:
        n_approved = random.randint(1, len(projects))
        approved = random.sample(projects, n_approved)
        pref_lines.append(f'{v}: {", ".join(approved)}')
    preferences_text = '\n'.join(pref_lines)

    return str(budget), projects_text, preferences_text, warnings


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    return render_template('index.html', title='Fair Lotteries for PB')


@app.route('/demo', methods=['GET', 'POST'])
def demo():
    form = BudgetingForm()

    # ── "Fill Random" button ──────────────────────────────────────────────
    # rand_fill.data is True only when that specific submit button triggered the POST
    if form.rand_fill.data:
        n_v = form.rand_voters.data or 4
        n_p = form.rand_projects.data or 3
        budget_str, projects_text, prefs_text, warnings = _generate_random_input(n_v, n_p)
        for msg, cat in warnings:
            flash(msg, cat)
        # Fill the main form fields with the generated data and re-render the page
        form.budget.data = int(budget_str)
        form.projects.data = projects_text
        form.preferences.data = prefs_text
        return render_template('demo.html', title='Demo', form=form)

    # ── "Run Algorithm" button ────────────────────────────────────────────
    # validate_on_submit() checks both that it was a POST and that all fields pass validation
    if form.submit.data and form.validate_on_submit():
        budget = form.budget.data
        projects_raw = form.projects.data
        prefs_raw = form.preferences.data
        algo = form.algorithm.data

        # Parse the free-text textarea into structured dicts
        projects_costs, err = lw.parse_projects(projects_raw)
        if err:
            flash(f'Projects input error: {err}', 'danger')
            return render_template('demo.html', title='Demo', form=form)

        preferences, err = lw.parse_preferences(prefs_raw, projects_costs)
        if err:
            flash(f'Preferences input error: {err}', 'danger')
            return render_template('demo.html', title='Demo', form=form)

        # Build the list of algorithms to run — one or both
        algos_to_run = ['gcr', 'mes'] if algo == 'both' else [algo]
        runs = []
        all_logs = []

        for a in algos_to_run:
            # Work on copies so trimming for GCR doesn't affect the other algorithm
            pc = dict(projects_costs)
            pref = {v: dict(b) for v, b in preferences.items()}

            # GCR grows exponentially — trim projects and voters if over the limit
            if a == 'gcr':
                if len(pc) > GCR_MAX_PROJECTS:
                    keep = list(pc.keys())[:GCR_MAX_PROJECTS]
                    flash(
                        f'BW-GCR-PB runtime grows exponentially. '
                        f'Running with the first {GCR_MAX_PROJECTS} projects out of {len(pc)}.',
                        'warning'
                    )
                    pc = {k: pc[k] for k in keep}
                    # Remove trimmed projects from every voter's ballot
                    pref = {v: {k: b[k] for k in keep} for v, b in pref.items()}
                if len(pref) > GCR_MAX_VOTERS:
                    keep_v = list(pref.keys())[:GCR_MAX_VOTERS]
                    flash(
                        f'BW-GCR-PB runtime grows exponentially. '
                        f'Running with the first {GCR_MAX_VOTERS} voters out of {len(pref)}.',
                        'warning'
                    )
                    pref = {v: pref[v] for v in keep_v}

            try:
                prob_pairs, selected, satisfactions, logs = lw.run_algorithm(budget, pc, pref, a)
            except ValueError as e:
                flash(f'Algorithm error ({a.upper()}): {e}', 'danger')
                return render_template('demo.html', title='Demo', form=form)
            except Exception as e:
                flash(f'Unexpected error ({a.upper()}): {e}', 'danger')
                return render_template('demo.html', title='Demo', form=form)

            # Collect logs with a header so the /logs page separates them clearly
            all_logs.append(f'=== {a.upper()} ===\n{logs}')
            guarantee = 'Full Justified Representation (FJR)' if a == 'gcr' else 'Extended Justified Representation (EJR)'
            # Each run is a dict with everything result.html needs to display
            runs.append({
                'algo_label': 'BW-GCR-PB' if a == 'gcr' else 'BW-MES-PB',
                'guarantee': guarantee,
                'prob_pairs': prob_pairs,
                'selected': selected,
                'satisfactions': satisfactions,
                'projects_costs': pc,
                'preferences': pref,
            })

        # Store combined logs as an attribute on the function for the /logs route
        lw.run_algorithm.last_logs = '\n\n'.join(all_logs)

        return render_template(
            'result.html',
            title='Result',
            budget=budget,
            projects_costs=projects_costs,
            preferences=preferences,
            runs=runs,
        )

    # First GET visit or POST with invalid form — show the empty/re-populated form
    return render_template('demo.html', title='Demo', form=form)


@app.route('/logs')
def logs():
    # Return raw log text — mimetype text/plain prevents the browser from interpreting HTML tags
    content = lw.run_algorithm.last_logs or '(No logs yet — run the algorithm first.)'
    return Response(content, mimetype='text/plain; charset=utf-8')


@app.route('/about')
def about():
    return render_template('about.html', title='About')
