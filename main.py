from flask import Flask, current_app, render_template, request, redirect, session, url_for, flash
from pathlib import Path
from datetime import datetime
from functools import wraps
import sqlite3

app = Flask(__name__)
app.secret_key = "Group6WebProgramming"
with app.app_context():
    DATABASE = Path(current_app.root_path) / 'db' / 'Group6WP.db'


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'idCanBo' not in session:
            flash("Bạn cần đăng nhập để xem trang này.", "error")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def super_admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('is_super_admin'):
            flash("Bạn không có quyền truy cập trang này.", "error")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not (session.get('is_super_admin') or session.get('is_khoa_admin')):
            flash("Bạn không có quyền truy cập trang này.", "error")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


@app.route("/", methods=["GET", "POST"])
def login():
    if 'idCanBo' in session:
        if session.get('is_super_admin') or session.get('is_khoa_admin'):
            return redirect(url_for("admin_home"))
        return redirect(url_for("giangvien", idCanBo=session['idCanBo']))

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        conn = get_db()
        taikhoan = conn.execute(
            "SELECT * FROM TaiKhoan WHERE TenDangNhap=? AND Password=?",
            (username, password)
        ).fetchone()
        if taikhoan:
            idTaiKhoan = taikhoan["ID"]
            canbo = conn.execute(
                "SELECT * FROM CanBo WHERE IDTaiKhoan=?",
                (idTaiKhoan,)
            ).fetchone()
            if canbo is None:
                flash("Tài khoản chưa được liên kết với cán bộ.", "error")
                return render_template("login.html")

            idCanBo = canbo["ID"]
            session['idCanBo'] = idCanBo
            session['ten_canbo'] = canbo["Ten"]
            session['is_super_admin'] = False
            session['is_khoa_admin'] = False

            superAdmin = conn.execute("SELECT * FROM Admin WHERE IDCanBo=?", (idCanBo,)).fetchone()
            if superAdmin:
                session['is_super_admin'] = True

            khoaAdmin = conn.execute("SELECT * FROM CanBo WHERE ID=? AND LaAdminKhoa=1", (idCanBo,)).fetchone()
            if khoaAdmin:
                session['is_khoa_admin'] = True

            if superAdmin or khoaAdmin:
                return redirect(url_for("admin_home"))
            else:
                return redirect(url_for("giangvien", idCanBo=idCanBo))
        else:
            flash("Tên đăng nhập hoặc mật khẩu không đúng.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Đăng xuất thành công.", "success")
    return redirect(url_for("login"))


@app.route("/giangvien")
@app.route("/giangvien/<int:idCanBo>")
@login_required
def giangvien(idCanBo=None):
    if idCanBo is None:
        idCanBo = session.get('idCanBo')
    conn = get_db()
    canbo = conn.execute("SELECT Ten FROM CanBo WHERE ID=?", (idCanBo,)).fetchone()
    hocphan = conn.execute("""
        SELECT HocPhan.ID, HocPhan.Ten, HocPhan.DeCuong, CanBo_HocPhan.ThoiGian
        FROM CanBo_HocPhan
        JOIN HocPhan ON HocPhan.ID = CanBo_HocPhan.IDHocPhan
        WHERE CanBo_HocPhan.IDCanBo = ?
    """, (idCanBo,)).fetchall()
    return render_template("giangvien.html", hocphan=hocphan, canbo=canbo)


@app.route("/admin")
@admin_required
def admin_home():
    return render_template("admin_home.html")


@app.route("/admin/users", methods=["GET", "POST"])
@super_admin_required
def admin_users():
    conn = get_db()
    if request.method == "POST":
        canbo_id = request.form["canbo_id"]
        current_status = int(request.form.get("admin_status", 0))
        new_status = 0 if current_status == 1 else 1
        conn.execute("UPDATE CanBo SET LaAdminKhoa = ? WHERE ID = ?", (new_status, canbo_id))
        conn.commit()
        flash("Cập nhật quyền Admin Khoa thành công.", "success")
        return redirect(url_for("admin_users"))

    users = conn.execute("""
        SELECT CanBo.ID AS CanBoID,
               CanBo.Ten AS TenCanBo,
               TenDangNhap,
               DonVi.Ten AS Khoa,
               LaAdminKhoa
        FROM CanBo
        JOIN TaiKhoan ON TaiKhoan.ID = CanBo.IDTaiKhoan
        LEFT JOIN DonVi ON DonVi.ID = CanBo.IDKhoa
    """).fetchall()
    return render_template("admin_users.html", users=users)


@app.route("/admin/subjects", methods=["GET", "POST"])
@super_admin_required
def admin_subjects():
    conn = get_db()
    if request.method == "POST":
        subject_id = request.form["subject_id"]
        khoa_id = request.form["khoa_id"]
        conn.execute("UPDATE HocPhan SET IDKhoa=? WHERE ID=?", (khoa_id, subject_id))
        conn.commit()
        flash("Cập nhật môn học thành công.", "success")
        return redirect(url_for("admin_subjects"))

    subjects = conn.execute("""
        SELECT HocPhan.ID, HocPhan.Ten, DonVi.Ten AS Khoa
        FROM HocPhan
        LEFT JOIN DonVi ON DonVi.ID = HocPhan.IDKhoa
    """).fetchall()
    khoa_list = conn.execute("SELECT ID, Ten FROM DonVi").fetchall()
    return render_template("admin_subjects.html", subjects=subjects, khoa_list=khoa_list)


@app.route("/khoa/subjects")
@app.route("/khoa/<int:khoa_id>/subjects")
@login_required
def khoa_subjects(khoa_id=None):
    conn = get_db()
    if khoa_id is None:
        requesterID = conn.execute("SELECT IDKhoa FROM CanBo WHERE ID=?", (session['idCanBo'],)).fetchone()
        if requesterID is None:
            flash("Không tìm thấy khoa của giảng viên.", "error")
            return redirect(url_for("giangvien", idCanBo=session['idCanBo']))
        khoa_id = requesterID["IDKhoa"]

    subjects = conn.execute("SELECT ID, Ten FROM HocPhan WHERE IDKhoa=?", (khoa_id,)).fetchall()
    khoa = conn.execute("SELECT Ten FROM DonVi WHERE ID=?", (khoa_id,)).fetchone()
    return render_template(
        "khoa_subjects.html",
        subjects=subjects,
        khoa_name=khoa["Ten"],
        khoa_id=khoa_id
    )


@app.route("/khoa/<int:khoa_id>/subject/<int:subject_id>/lecturers", methods=["GET", "POST"])
@login_required
def edit_lecturers(khoa_id, subject_id):
    conn = get_db()
    if request.method == "POST":
        systemTime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("DELETE FROM CanBo_HocPhan WHERE IDHocPhan=?", (subject_id,))
        selected = request.form.getlist("lecturer_ids")
        for cb_id in selected:
            conn.execute(
                "INSERT INTO CanBo_HocPhan (IDCanBo, IDHocPhan, ThoiGian) VALUES (?, ?, ?)",
                (cb_id, subject_id, systemTime)
            )
        conn.commit()
        flash("Cập nhật giảng viên cho môn học thành công.", "success")
        return redirect(url_for('khoa_subjects', khoa_id=khoa_id))

    current = conn.execute("""
        SELECT CanBo.ID, CanBo.Ten
        FROM CanBo_HocPhan
        JOIN CanBo ON CanBo.ID = CanBo_HocPhan.IDCanBo
        WHERE CanBo_HocPhan.IDHocPhan=?
    """, (subject_id,)).fetchall()
    current_ids = {row["ID"] for row in current}

    all_lecturers = conn.execute("""
        SELECT CanBo.ID, CanBo.Ten, DonVi.Ten AS Khoa, LoaiGiangVien.Ten AS LoaiGV
        FROM CanBo
        LEFT JOIN DonVi ON DonVi.ID = CanBo.IDKhoa
        LEFT JOIN LoaiGiangVien ON LoaiGiangVien.ID = CanBo.LoaiGiangVien
        ORDER BY CanBo.Ten
    """).fetchall()

    subject = conn.execute("SELECT Ten FROM HocPhan WHERE ID=?", (subject_id,)).fetchone()
    return render_template(
        "edit_lecturers.html",
        subject_name=subject["Ten"],
        all_lecturers=all_lecturers,
        current_ids=current_ids,
        khoa_id=khoa_id,
        subject_id=subject_id
    )


if __name__ == "__main__":
    app.run(debug=True)
