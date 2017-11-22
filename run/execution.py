# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import sys
import click
import select
import random
import subprocess
from . import helpers


# Module API

class ExecutionPlan(object):

    # Public

    def __init__(self, commands, mode):
        self._commands = commands
        self._mode = mode

    def explain(self):

        # Compose
        lines = []
        plain = True
        for command in self._commands:
            if self._mode in ['sequence', 'parallel', 'multiplex']:
                if not command.variable:
                    if plain:
                        lines.append('[%s]' % self._mode.upper())
                    plain = False
            code = command.code
            if command.variable:
                code = '%s="%s"' % (command.variable, command.code)
            lines.append('%s$ %s' % (' '*(0 if plain else 4), code))

        return '\n'.join(lines)

    def execute(self):

        # Setup
        commands = []
        for command in self._commands:
            if command.variable:
                _execute_variable(command)
                continue
            commands.append(command)

        # Directive
        if self._mode == 'directive':
            _execute_directive(commands[0])

        # Sequence
        elif self._mode == 'sequence':
            _execute_sequence(commands)

        # Parallel
        elif self._mode == 'parallel':
            _execute_parallel(commands)

        # Multiplex
        elif self._mode == 'multiplex':
            _execute_multiplex(commands)


class Command(object):

    # Public

    def __init__(self, name, code, variable=None):
        self._name = name
        self._code = code
        self._variable = variable

    @property
    def name(self):
        return self._name

    @property
    def code(self):
        return self._code

    @code.setter
    def code(self, value):
        self._code = value

    @property
    def variable(self):
        return self._variable


# Internal

def _execute_variable(command):

    # Execute process
    try:
        output = subprocess.check_output(command.code, shell=True)
    except subprocess.CalledProcessError:
        message = 'Command "%s" has failed' % command.code
        helpers.print_message('general', message=message)
        exit(1)
    os.environ[command.variable] = output.decode('utf-8').strip()


def _execute_directive(command):

    # Execute process
    returncode = subprocess.check_call(command.code, shell=True)
    if returncode != 0:
        message = 'Command "%s" has failed' % command.code
        helpers.print_message('general', message=message)
        exit(1)


def _execute_sequence(commands):

    # Execute process
    for command in commands:
        if command.variable:
            _execute_variable(command)
            continue
        _execute_directive(command)


def _execute_parallel(commands):

    # Start processes
    processes = []
    for command in commands:
        process = subprocess.Popen(command.code, shell=True, stdout=subprocess.PIPE)
        processes.append((command, process))

    # Wait processes
    for command, process in processes:
        output, errput = process.communicate()
        sys.stdout.write(output.decode('utf-8'))
        if process.returncode != 0:
            message = 'Command "%s" has failed' % command.code
            helpers.print_message('general', message=message)
            exit(1)


def _execute_multiplex(commands):

    # Start processes
    processes = []
    for command in commands:
        process = subprocess.Popen(command.code, shell=True, stdout=subprocess.PIPE)
        poll = select.poll()
        processes.append((command, poll, random.choice(['red', 'green'])))
        poll.register(process.stdout, select.POLLIN)

    # Wait processes
    while True:
        if not processes:
            break
        for index, (command, poll, color) in list(enumerate(processes)):
            if poll.poll(1):
                line = process.stdout.readline().decode('utf-8')
                text = click.style('%s: %s' % (command.name, line), fg=color)
                click.echo(text, nl=False)
            if process.poll() is not None:
                processes.pop(index)
                if process.returncode != 0:
                    message = 'Command "%s" has failed' % command.code
                    helpers.print_message('general', message=message)
                    exit(1)