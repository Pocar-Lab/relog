"""
People pages: contacts list, user profile, and edit user.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

from src.auth import get_db, Role, role_required


people = Blueprint('people', __name__)

def is_admin():
    return current_user.role == Role.Admin
def can_edit(user):
    return is_admin() or current_user.user == user

def get_person(user):
    with get_db() as conn:
        person = conn.execute("SELECT * FROM people WHERE user = ?", (user,)).fetchone()
    if not person:
        abort(404)
    return person


@people.route('/people')
@role_required(Role.Guest)
def contacts():
    with get_db() as conn:
        rows = conn.execute("SELECT user, name, email, role FROM people ORDER BY name").fetchall()
    return render_template('people.html', people=rows, title='People')


@people.route('/people/<string:user>')
@login_required
def profile(user):
    if current_user.role < Role.Guest and not can_edit(user):
        abort(403)
    person = get_person(user)
    return render_template('profile.html', person=person, title=person['name'],
                           can_edit=can_edit(user))

# Edit user

@people.route('/people/<string:user>/edit')
@login_required
def edit(user):
    if not can_edit(user):
        abort(403)
    person = get_person(user)
    return render_template('edit_user.html', person=person, title=f"Edit {person['name']}",
                           roles=[r.name for r in Role],
                           is_admin=is_admin(),
                           is_self=(user == current_user.user))

@people.post('/people/<string:user>/edit')
@login_required
def edit_post(user):
    if not can_edit(user):
        abort(403)
    person = get_person(user)
    back = url_for('people.edit', user=user)

    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip().lower()
    if not name or not email:
        flash('Name and e-mail cannot be empty')
        return redirect(back)

    with get_db() as conn:
        taken = conn.execute("SELECT 1 FROM people WHERE email = ? AND user != ?",
                             (email, user)).fetchone()
    if taken:
        flash('That e-mail is already used by another account')
        return redirect(back)

    # Only admins can change roles
    role = person['role']
    if is_admin():
        role = Role[request.form.get('role', role)]
        if role not in Role:
            flash('Unknown role')
            return redirect(back)

    password = person['password']
    new_password = request.form.get('new_password', '')
    if new_password:
        if user == current_user.user:
            if not check_password_hash(person['password'], request.form.get('current_password', '')):
                flash('Current password is incorrect')
                return redirect(back)
        password = generate_password_hash(new_password)

    with get_db() as conn:
        conn.execute("UPDATE people SET name = ?, email = ?, role = ?, password = ? WHERE user = ?",
                     (name, email, role.value, password, user))

    flash('Saved')
    return redirect(url_for('people.profile', user=user))
