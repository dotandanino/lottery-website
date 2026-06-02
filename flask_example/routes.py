import random
import string

from flask import render_template, redirect, url_for, flash, request, Response
from flask_example import app
from flask_example.forms import BudgetingForm
from flask_example import lottery_wrapper as lw


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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

GCR_MAX_PROJECTS = 10
GCR_MAX_VOTERS   = 20


def _generate_random_input(n_voters, n_projects):
    """
    Return (budget_str, projects_text, preferences_text, warnings) with random data.
    warnings is a list of (message, category) tuples to flash.
    """
    warnings = []

    if n_projects <= len(_PROJECT_NAMES):
        projects = random.sample(_PROJECT_NAMES, n_projects)
    else:
        projects = list(_PROJECT_NAMES) + [
            f'Project_{i}' for i in range(1, n_projects - len(_PROJECT_NAMES) + 1)
        ]

    if n_voters <= len(_VOTER_NAMES):
        voters = random.sample(_VOTER_NAMES, n_voters)
    else:
        extra = [f'Voter_{i}' for i in range(1, n_voters - len(_VOTER_NAMES) + 1)]
        voters = list(_VOTER_NAMES) + extra

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

    base_cost = random.randint(3, 12) * 1000
    costs = {p: random.randint(1, 5) * base_cost for p in projects}
    total_cost = sum(costs.values())
    budget = random.randint(
        max(min(costs.values()), total_cost // (n_projects + 1)),
        max(total_cost * 2 // 3, min(costs.values()) * 2)
    )

    projects_text = '\n'.join(f'{p}: {c}' for p, c in costs.items())

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

    # Handle "Fill Random" button
    if form.rand_fill.data:
        n_v = form.rand_voters.data or 4
        n_p = form.rand_projects.data or 3
        budget_str, projects_text, prefs_text, warnings = _generate_random_input(n_v, n_p)
        for msg, cat in warnings:
            flash(msg, cat)
        form.budget.data = int(budget_str)
        form.projects.data = projects_text
        form.preferences.data = prefs_text
        return render_template('demo.html', title='Demo', form=form)

    # Handle "Run Algorithm" button
    if form.submit.data and form.validate_on_submit():
        budget = form.budget.data
        projects_raw = form.projects.data
        prefs_raw = form.preferences.data
        algo = form.algorithm.data

        projects_costs, err = lw.parse_projects(projects_raw)
        if err:
            flash(f'Projects input error: {err}', 'danger')
            return render_template('demo.html', title='Demo', form=form)

        preferences, err = lw.parse_preferences(prefs_raw, projects_costs)
        if err:
            flash(f'Preferences input error: {err}', 'danger')
            return render_template('demo.html', title='Demo', form=form)

        algos_to_run = ['gcr', 'mes'] if algo == 'both' else [algo]
        runs = []
        all_logs = []

        for a in algos_to_run:
            pc = dict(projects_costs)
            pref = {v: dict(b) for v, b in preferences.items()}

            if a == 'gcr':
                if len(pc) > GCR_MAX_PROJECTS:
                    keep = list(pc.keys())[:GCR_MAX_PROJECTS]
                    flash(
                        f'BW-GCR-PB runtime grows exponentially. '
                        f'Running with the first {GCR_MAX_PROJECTS} projects out of {len(pc)}.',
                        'warning'
                    )
                    pc = {k: pc[k] for k in keep}
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

            all_logs.append(f'=== {a.upper()} ===\n{logs}')
            guarantee = 'Full Justified Representation (FJR)' if a == 'gcr' else 'Extended Justified Representation (EJR)'
            runs.append({
                'algo_label': 'BW-GCR-PB' if a == 'gcr' else 'BW-MES-PB',
                'guarantee': guarantee,
                'prob_pairs': prob_pairs,
                'selected': selected,
                'satisfactions': satisfactions,
                'projects_costs': pc,
                'preferences': pref,
            })

        lw.run_algorithm.last_logs = '\n\n'.join(all_logs)

        return render_template(
            'result.html',
            title='Result',
            budget=budget,
            projects_costs=projects_costs,
            preferences=preferences,
            runs=runs,
        )

    # First GET or invalid form resubmission
    return render_template('demo.html', title='Demo', form=form)


@app.route('/logs')
def logs():
    content = lw.run_algorithm.last_logs or '(No logs yet — run the algorithm first.)'
    return Response(content, mimetype='text/plain; charset=utf-8')


@app.route('/about')
def about():
    return render_template('about.html', title='About')
