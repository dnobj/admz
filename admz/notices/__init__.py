"""Notices: a small durable attention queue (ADR-0071).

A notice is the thing that stays *open* until someone deals with it. Tasks and
drift checks raise them (:mod:`admz.notices.producers`); the Console lists them
and turns one into a conversation (``admz/api/routes/notices.py``); the store is
:mod:`admz.notices.store`.
"""
