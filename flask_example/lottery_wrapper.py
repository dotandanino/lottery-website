import logging
import sys
import os
from io import StringIO

# Add the project root to PATH so pabutools can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from pabutools.rules.lottery import (
    BW_GCR_PB_wrapped,   # GCR algorithm — returns a lottery with FJR guarantee
    BW_MES_PB_wrapped,   # MES algorithm — returns a lottery with EJR guarantee
    build_instance,       # builds an Instance (project list + budget limit)
    build_profile,        # builds a Profile (voter approval ballots)
)
# Import the algorithm's internal logger so we can capture its log messages
from pabutools.rules.lottery.lottery_rule import logger as algo_logger


def parse_projects(text):
    """
    Parse the projects textarea into a dict {name: cost}.
    Expected format (one per line):  ProjectName: cost
    Returns (projects_costs, error_message) — one of them is always None.
    """
    projects_costs = {}
    # Iterate line by line over the text the user entered
    for lineno, line in enumerate(text.strip().splitlines(), 1):
        line = line.strip()
        if not line:
            continue  # skip blank lines
        if ':' not in line:
            return None, f'Line {lineno}: expected "Name: cost", got "{line}"'
        # Split on the first ':' only (partition is safer than split(':'))
        name, _, cost_str = line.partition(':')
        name = name.strip()
        cost_str = cost_str.strip()
        if not name:
            return None, f'Line {lineno}: project name is empty'
        try:
            cost = int(cost_str)
        except ValueError:
            return None, f'Line {lineno}: cost "{cost_str}" is not a valid integer'
        if cost <= 0:
            return None, f'Line {lineno}: cost must be positive, got {cost}'
        projects_costs[name] = cost
    if not projects_costs:
        return None, 'No projects found. Please enter at least one project.'
    return projects_costs, None


def parse_preferences(text, valid_projects):
    """
    Parse the preferences textarea into a dict {voter: {project: 0/1}}.
    Expected format (one per line):  VoterName: proj1, proj2
    Returns (preferences, error_message) — one of them is always None.
    """
    preferences = {}
    for lineno, line in enumerate(text.strip().splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        if ':' not in line:
            return None, f'Line {lineno}: expected "Voter: project1,project2", got "{line}"'
        voter, _, proj_str = line.partition(':')
        voter = voter.strip()
        if not voter:
            return None, f'Line {lineno}: voter name is empty'
        # Collect the projects this voter approved
        approved = set()
        for p in proj_str.split(','):
            p = p.strip()
            if not p:
                continue
            if p not in valid_projects:
                return None, f'Line {lineno}: project "{p}" not found in projects list'
            approved.add(p)
        # Build a binary ballot: 1 if approved, 0 otherwise — for every known project
        ballot = {p: (1 if p in approved else 0) for p in valid_projects}
        preferences[voter] = ballot
    if not preferences:
        return None, 'No voters found. Please enter at least one voter.'
    return preferences, None


def run_algorithm(budget, projects_costs, preferences, algorithm_choice):
    """
    Run the selected algorithm and return results.

    Returns
    -------
    tuple: (prob_pairs, selected_names, voter_satisfactions, logs_text)
        prob_pairs          — list of (project_name, probability) for each project
        selected_names      — names of projects chosen in the lottery draw
        voter_satisfactions — {voter: [approved projects that were selected]}
        logs_text           — log messages emitted by the algorithm during execution
    """
    # Create an in-memory buffer to capture log output instead of printing to the terminal
    log_stream = StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setFormatter(logging.Formatter(
        '%(asctime)s  %(levelname)-8s  %(name)s:%(lineno)d  %(message)s'
    ))
    # Attach the handler to the algorithm's internal logger
    algo_logger.addHandler(handler)
    algo_logger.setLevel(logging.DEBUG)

    try:
        # Build the data structures the algorithm expects
        instance = build_instance(list(projects_costs.keys()), projects_costs, budget)
        profile = build_profile(list(preferences.keys()), preferences, instance)

        # Run the chosen algorithm
        if algorithm_choice == 'gcr':
            p_vec, selected = BW_GCR_PB_wrapped(instance, profile)
        else:
            p_vec, selected = BW_MES_PB_wrapped(instance, profile)

        # p_vec is indexed over projects in alphabetical order (same order as _generic_pb_wrapper)
        sorted_projects = sorted(instance, key=lambda p: p.name)
        prob_pairs = [(proj.name, round(float(prob), 4)) for proj, prob in zip(sorted_projects, p_vec)]

        # Names of the projects actually chosen in the lottery draw
        selected_names = [p.name for p in selected]

        # For each voter — which of their approved projects were selected
        voter_satisfactions = {}
        for voter, ballot in preferences.items():
            approved_selected = [p for p, v in ballot.items() if v == 1 and p in selected_names]
            voter_satisfactions[voter] = approved_selected

    finally:
        # Always detach the handler — even if an exception was raised
        algo_logger.removeHandler(handler)

    logs_text = log_stream.getvalue()
    return prob_pairs, selected_names, voter_satisfactions, logs_text


# Attribute on the function itself — stores the last logs for the /logs route
run_algorithm.last_logs = ''
