"""Thin Goal Record projection, one-step admission, and proof validation.

This module returns bounded local decisions. It never mutates a host, schedules
work, creates agents, or turns an admitted action into execution evidence.
"""
from __future__ import annotations

import copy
import re


__all__ = [
    'GOAL_LOOP_VERSION',
    'GoalLoopError',
    'build_goal_record',
    'next_action',
    'validate_acceptance',
]

GOAL_LOOP_VERSION = 'GOAL_LOOP_V1'
PROTECTED_EFFECTS = (
    'commit',
    'push',
    'release',
    'deploy',
    'production',
    'delete',
    'permission_expansion',
)
ACTION_FIELDS = {
    'effect',
    'surface',
    'expected_candidate_sha256',
    'closes_criterion_id',
}
EFFECT_METHODS = {
    'local_modify': {'user_path', 'git_observation', 'independent_review'},
    'visual_modify': {'user_path', 'visual_observation', 'independent_review'},
    'build': {'artifact_validation'},
    'install': {'install_observation'},
    'commit': {'git_commit_observation'},
    'push': {'remote_ref_observation'},
    'release': {'release_observation'},
    'deploy': {'deployment_observation'},
    'production': {'production_observation'},
    'delete': {'deletion_observation'},
    'permission_expansion': {'permission_observation'},
}


class GoalLoopError(ValueError):
    pass


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _hex(value, length):
    return isinstance(value, str) and re.fullmatch(rf'[a-f0-9]{{{length}}}', value) is not None


def _host_complete(value):
    return (
        isinstance(value, dict)
        and all(_text(value.get(key)) for key in ('root_id', 'path', 'repository'))
        and _hex(value.get('revision'), 40)
    )


def _references_complete(values):
    return (
        isinstance(values, list)
        and all(
            isinstance(value, dict)
            and _text(value.get('repository'))
            and _hex(value.get('revision'), 40)
            and _text(value.get('purpose'))
            and value.get('access') == 'read_only'
            for value in values
        )
    )


def build_goal_record(project, plan, work_id, host_observation, authorizations):
    """Project existing state plus fresh host facts into one non-persisted view."""
    if not isinstance(project, dict) or not isinstance(plan, dict):
        raise GoalLoopError('project and plan must be objects')
    if plan.get('goal_status') != 'confirmed' or not _text(plan.get('final_goal')):
        raise GoalLoopError('Goal Record requires a confirmed goal')

    matches = [
        work for work in plan.get('work_items', [])
        if isinstance(work, dict) and work.get('work_id') == work_id
    ]
    if len(matches) != 1:
        raise GoalLoopError('Goal Record requires exactly one work item')
    work = matches[0]
    if not _host_complete(host_observation):
        raise GoalLoopError('delivery host identity is incomplete')
    if not _hex(work.get('input_sha256'), 64):
        raise GoalLoopError('work item requires a 64-hex candidate input digest')

    references = work.get('reference_sources', [])
    if not isinstance(references, list):
        raise GoalLoopError('reference_sources must be a list')
    for reference in references:
        if not isinstance(reference, dict) or not _text(reference.get('repository')) or not _text(reference.get('purpose')):
            raise GoalLoopError('reference identity and purpose are required')
        if not _hex(reference.get('revision'), 40):
            raise GoalLoopError('reference requires a full 40-hex revision')
        if reference.get('access') != 'read_only':
            raise GoalLoopError('reference access must be read_only')
        if reference['repository'] == host_observation['repository']:
            raise GoalLoopError('delivery host and reference repositories must be distinct')

    write_surface = work.get('write_surface')
    if not isinstance(write_surface, list) or any(not _text(path) for path in write_surface):
        raise GoalLoopError('write_surface must contain named paths')
    if len(set(write_surface)) != len(write_surface):
        raise GoalLoopError('write_surface paths must be unique')

    permissions = {
        effect: {'status': 'not_granted', 'surfaces': []}
        for effect in PROTECTED_EFFECTS
    }
    if not isinstance(authorizations, list):
        raise GoalLoopError('authorizations must be a list')
    seen_effects = set()
    for authorization in authorizations:
        if not isinstance(authorization, dict) or not _text(authorization.get('effect')):
            raise GoalLoopError('authorization effect is required')
        effect = authorization['effect']
        if effect in seen_effects:
            raise GoalLoopError('authorization effect must be unique')
        seen_effects.add(effect)
        surfaces = authorization.get('surfaces')
        if (
            not isinstance(surfaces, list)
            or not surfaces
            or any(not _text(surface) for surface in surfaces)
        ):
            raise GoalLoopError('authorization surfaces are required')
        if any(surface not in write_surface for surface in surfaces):
            raise GoalLoopError('authorization surface is outside write_surface')
        if not _text(authorization.get('decision_ref')):
            raise GoalLoopError('authorization decision_ref is required')
        permissions[effect] = {
            'status': 'granted',
            'surfaces': list(surfaces),
            'decision_ref': authorization['decision_ref'],
        }

    all_criteria = plan.get('acceptance_criteria')
    if not isinstance(all_criteria, list) or not all_criteria:
        raise GoalLoopError('acceptance criteria are required')
    criterion_ids = []
    for criterion in all_criteria:
        if not isinstance(criterion, dict) or not _text(criterion.get('criterion_id')):
            raise GoalLoopError('acceptance criterion identity is required')
        criterion_ids.append(criterion['criterion_id'])
    if len(set(criterion_ids)) != len(criterion_ids):
        raise GoalLoopError('acceptance criterion identities must be unique')
    acceptance_ids = work.get('acceptance_ids')
    if acceptance_ids is None:
        acceptance_ids = criterion_ids
    if (
        not isinstance(acceptance_ids, list)
        or not acceptance_ids
        or len(set(acceptance_ids)) != len(acceptance_ids)
        or any(value not in criterion_ids for value in acceptance_ids)
    ):
        raise GoalLoopError('current work acceptance_ids must bind known criteria')
    criteria = [
        criterion for criterion in all_criteria
        if criterion['criterion_id'] in set(acceptance_ids)
    ]

    proof_gaps = [
        criterion['criterion_id']
        for criterion in criteria
        if criterion.get('status') not in {'accepted', 'completed'}
    ]
    return {
        'version': GOAL_LOOP_VERSION,
        'goal': plan['final_goal'],
        'non_goals': copy.deepcopy(plan.get('non_goals', [])),
        'criteria': copy.deepcopy(criteria),
        'current_work': copy.deepcopy(work),
        'write_surface': list(write_surface),
        'delivery_host': copy.deepcopy(host_observation),
        'references': copy.deepcopy(references),
        'permissions': permissions,
        'candidate_sha256': work['input_sha256'],
        'risk': copy.deepcopy(work.get('risk')),
        'review': copy.deepcopy(work.get('review')),
        'proof_gaps': proof_gaps,
        'stop_condition': 'all criteria have current proof',
    }


def next_action(goal_record, proposed_action, proof_state):
    """Return one bounded verdict; never perform or schedule the action."""
    if not isinstance(goal_record, dict) or goal_record.get('version') != GOAL_LOOP_VERSION:
        raise GoalLoopError('a GOAL_LOOP_V1 record is required')
    if not isinstance(proposed_action, dict):
        raise GoalLoopError('exactly one proposed action is required')
    if set(proposed_action) != ACTION_FIELDS:
        raise GoalLoopError('proposed action must contain exactly the four action fields')
    if not isinstance(proof_state, dict):
        raise GoalLoopError('proof_state must be an object')

    criteria = {
        criterion.get('criterion_id')
        for criterion in goal_record.get('criteria', [])
        if isinstance(criterion, dict) and _text(criterion.get('criterion_id'))
    }
    if not _host_complete(goal_record.get('delivery_host')) or not _references_complete(goal_record.get('references')):
        return {
            'verdict': 'EVIDENCE_REQUIRED',
            'action': None,
            'reason': 'delivery host or reference identity is incomplete',
        }
    accepted_claims = proof_state.get('accepted_claims', [])
    if not isinstance(accepted_claims, list) or any(
        not isinstance(value, dict) for value in accepted_claims
    ):
        raise GoalLoopError('accepted claim receipts must be a list of objects')
    accepted = {
        value.get('criterion_id')
        for value in accepted_claims
        if value.get('status') == 'ACCEPTED'
        and value.get('candidate_sha256') == goal_record.get('candidate_sha256')
        and value.get('criterion_id') in criteria
    }
    if criteria and criteria.issubset(accepted):
        return {
            'verdict': 'STOP_ACCEPTED',
            'action': None,
            'reason': 'all criteria have current proof',
        }
    if _text(proof_state.get('material_decision')):
        return {
            'verdict': 'DECISION_REQUIRED',
            'action': None,
            'reason': 'one material decision controls the result',
        }

    if proposed_action.get('expected_candidate_sha256') != goal_record.get('candidate_sha256'):
        raise GoalLoopError('proposed action candidate does not match the Goal Record')
    criterion_id = proposed_action.get('closes_criterion_id')
    if criterion_id not in criteria or criterion_id in set(accepted):
        raise GoalLoopError('proposed action must close one current criterion gap')
    effect = proposed_action.get('effect')
    surface = proposed_action.get('surface')
    if not _text(effect) or not _text(surface):
        raise GoalLoopError('proposed action effect and surface are required')
    permission = goal_record.get('permissions', {}).get(effect, {})
    if permission.get('status') != 'granted' or surface not in permission.get('surfaces', []):
        return {
            'verdict': 'PERMISSION_REQUIRED',
            'action': None,
            'reason': 'effect is not granted for the requested surface',
        }
    return {
        'verdict': 'ACTION_READY',
        'action': copy.deepcopy(proposed_action),
        'reason': 'one admitted action closes the next proof gap',
    }


def validate_acceptance(goal_record, claim, observation, proof_validator):
    """Validate one candidate-bound observed claim without changing state."""
    if not isinstance(goal_record, dict) or goal_record.get('version') != GOAL_LOOP_VERSION:
        raise GoalLoopError('a GOAL_LOOP_V1 record is required')
    if not isinstance(claim, dict) or not isinstance(observation, dict):
        raise GoalLoopError('claim and observation must be objects')
    if not callable(proof_validator):
        raise GoalLoopError('proof_validator must be callable')

    criterion_id = claim.get('criterion_id')
    criterion_ids = {
        criterion.get('criterion_id')
        for criterion in goal_record.get('criteria', [])
        if isinstance(criterion, dict)
    }
    if criterion_id not in criterion_ids:
        raise GoalLoopError('claim criterion does not belong to the Goal Record')

    host_root_id = goal_record.get('delivery_host', {}).get('root_id')
    if claim.get('host_root_id') != host_root_id:
        raise GoalLoopError('claim host does not match the delivery host')
    if observation.get('host_root_id') != host_root_id:
        raise GoalLoopError('observed host does not match the delivery host')

    candidate = goal_record.get('candidate_sha256')
    if claim.get('candidate_sha256') != candidate:
        raise GoalLoopError('claim candidate does not match the Goal Record')
    if observation.get('candidate_sha256') != candidate:
        raise GoalLoopError('observation candidate is stale or mismatched')

    effect = claim.get('effect')
    surface = claim.get('surface')
    if observation.get('effect') != effect or observation.get('surface') != surface:
        raise GoalLoopError('claim effect or surface does not match the observation')
    permission = goal_record.get('permissions', {}).get(effect, {})
    if (
        permission.get('status') != 'granted'
        or surface not in permission.get('surfaces', [])
    ):
        raise GoalLoopError('claimed effect is not authorized for the surface')

    method = claim.get('method')
    if not _text(method) or observation.get('method') != method:
        raise GoalLoopError('claim method does not match the observation')
    if observation.get('user_path_available') is True and method != 'user_path':
        raise GoalLoopError('user_path proof is required when the real path is available')
    if method not in EFFECT_METHODS.get(effect, set()):
        raise GoalLoopError('claim method cannot prove the claimed effect')
    if claim.get('result') != 'passed' or observation.get('result') != 'passed':
        raise GoalLoopError('claim result and observed result must both be passed')
    if observation.get('observed_effect') is not True:
        raise GoalLoopError('observed effect is required; admission is not execution')
    observer_id = claim.get('observer_id')
    if not _text(observer_id) or observation.get('observer_id') != observer_id:
        raise GoalLoopError('claim observer does not match the observation')
    if method == 'independent_review':
        review = goal_record.get('review') or {}
        executor = goal_record.get('current_work', {}).get('executor') or {}
        if (
            review.get('mode') != 'independent'
            or observer_id != review.get('reviewer')
            or observer_id == executor.get('id')
        ):
            raise GoalLoopError('independent reviewer must be the registered non-writer')

    findings = claim.get('unresolved_findings')
    if not isinstance(findings, list) or findings:
        raise GoalLoopError('unresolved findings must be an empty list')
    proofs = claim.get('proofs')
    if not isinstance(proofs, list) or not proofs:
        raise GoalLoopError('claim proof list is required')
    if any(not isinstance(proof, dict) for proof in proofs):
        raise GoalLoopError('claim proof entries must be retained proof objects')
    expected_source_role = (
        'independent_reviewer' if method == 'independent_review'
        else 'delivery_host'
    )
    if any(proof.get('source_role') != expected_source_role for proof in proofs):
        raise GoalLoopError('proof source role does not match the claimed observation')
    proof_sha256s = [proof.get('sha256') for proof in proofs]
    if (
        any(not _hex(digest, 64) for digest in proof_sha256s)
        or observation.get('proof_sha256s') != proof_sha256s
    ):
        raise GoalLoopError('observed proof hashes do not match the claim')
    for proof in proofs:
        proof_validator(proof)

    return {
        'status': 'ACCEPTED',
        'criterion_id': criterion_id,
        'candidate_sha256': candidate,
    }
