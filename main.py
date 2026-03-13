from flask import Flask, current_app, render_template, request, redirect, session, url_for, flash
from pathlib import Path
from datetime import datetime
import sqlite3

app = Flask(__name__)
app.secret_key = "Group6WebProgramming"   
with app.app_context():
    DATABASE = Path(current_app.root_path) / 'db' / 'Group6WP.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

@app.route("/", methods=["GET","POST"])
def login():
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
            idCanBo = canbo["ID"]
            session['idCanBo'] = idCanBo
            session['is_super_admin'] = False
            session['is_khoa_admin'] = False
            superAdmin = conn.execute("SELECT * FROM Admin WHERE IDCanBo=?",(idCanBo,)).fetchone()
            if superAdmin:
                session['is_super_admin'] = True
                app.logger.debug(f"User {username} is a super admin. session data: {session}")
            khoaAdmin = conn.execute("SELECT * FROM CanBo WHERE ID=? AND LaAdminKhoa=1",(idCanBo,)).fetchone()
            if khoaAdmin:
                session['is_khoa_admin'] = True
                app.logger.debug(f"User {username} is a khoa admin. session data: {session}")
            
            if superAdmin or khoaAdmin:
                return redirect("/admin")
            else:
                return redirect(f"/giangvien/{idCanBo}")
        else:
            flash("Tên đăng nhập hoặc mật khẩu không đúng.", "error")
    return render_template("login.html")

# Người dùng đăng nhập thì sẽ thấy được đề cương mà mình được phân là hiệu chỉnh
# Khi đó, mỗi giảng viên login vào sẽ thấy danh sách đề cương mình được mời hiệu chỉnh
@app.route("/giangvien")
@app.route("/giangvien/<int:idCanBo>")
def giangvien(idCanBo = None):
    if idCanBo is None:
        idCanBo = session.get('idCanBo')
        if idCanBo is None:
            flash("Bạn cần đăng nhập để xem trang này.", "error")
            return redirect(url_for("login"))
    conn = get_db()
    # lấy học phần được phân quyền
    hocphan = conn.execute("""
        SELECT HocPhan.ID, HocPhan.Ten, CanBo_HocPhan.ThoiGian
        FROM CanBo_HocPhan
        JOIN HocPhan ON HocPhan.ID = CanBo_HocPhan.IDHocPhan
        WHERE CanBo_HocPhan.IDCanBo = ?
    """, (idCanBo,)).fetchall()
    return render_template("giangvien.html", hocphan=hocphan)

@app.route("/admin")
def admin_home():
    return render_template("admin_home.html")

# Admin gán (hiệu chỉnh) các môn học nào đi theo khoa nào.
@app.route("/admin/users", methods=["GET", "POST"])
def admin_users():
    conn = get_db()
    if request.method == "POST":
        app.logger.debug(f"Form data received: {request.form}")
        canbo_id = request.form["canbo_id"]
        if request.form.get("admin_status") == '1':
            app.logger.debug(f"Admin status checkbox is checked for CanBo ID {canbo_id}")
            adminKhoa = 0
        else:
            adminKhoa = 1

        conn.execute(
            "UPDATE CanBo SET LaAdminKhoa = ? WHERE ID = ?",
            (adminKhoa, canbo_id)
        )
        conn.commit()
        app.logger.debug(f"Updated CanBo ID {canbo_id} to admin status {adminKhoa}")
        flash("Cập nhật người dùng thành công.", "success")
        return redirect(url_for("admin_users"))
    users = conn.execute("""
        SELECT CanBo.ID AS CanBoID,
               TenDangNhap,
               DonVi.Ten AS Khoa,
               LaAdminKhoa
        FROM CanBo
        JOIN TaiKhoan ON TaiKhoan.ID = CanBo.IDTaiKhoan
        LEFT JOIN DonVi ON DonVi.ID = CanBo.IDKhoa
    """).fetchall()
    return render_template("admin_users.html", users=users)

# Admin vào nhìn thấy danh sách cá người dùng gán khoa nào và tích được người đó là quản trị của khoa
@app.route("/admin/subjects", methods=["GET", "POST"])
def admin_subjects():
    conn = get_db()
    if request.method == "POST":
        subject_id = request.form["subject_id"]
        khoa_id = request.form["khoa_id"]
        conn.execute(
            "UPDATE HocPhan SET IDKhoa=? WHERE ID=?",
            (khoa_id, subject_id)
        )
        conn.commit()
        flash("Cập nhật môn học thành công.", "success")
        return redirect(url_for("admin_subjects"))

    subjects = conn.execute("""
        SELECT HocPhan.ID, HocPhan.Ten, DonVi.Ten AS Khoa
        FROM HocPhan
        LEFT JOIN DonVi ON DonVi.ID = HocPhan.IDKhoa
    """).fetchall()
    khoa_list = conn.execute("SELECT ID, Ten FROM DonVi").fetchall()
    return render_template(
        "admin_subjects.html",
        subjects=subjects,
        khoa_list=khoa_list
    )

# Admin của Khoa (khác super admin) vào nhìn thấy danh sách các môn do khoa mình quản lý
@app.route("/khoa/subjects")
@app.route("/khoa/<int:khoa_id>/subjects")
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

# Với từng môn có thể chọn danh sách các giảng viên (kể cả ở khoa khác) vào để hiệu chỉnh
@app.route("/khoa/<int:khoa_id>/subject/<int:subject_id>/lecturers", methods=["GET", "POST"])
def edit_lecturers(khoa_id, subject_id):
    conn = get_db()
    if request.method == "POST":
        systemTime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # Clear existing assignments
        conn.execute(
            "DELETE FROM CanBo_HocPhan WHERE IDHocPhan=?",
            (subject_id,)
        )
        # Insert new assignments
        selected = request.form.getlist("lecturer_ids")
        for cb_id in selected:
            conn.execute(
                "INSERT INTO CanBo_HocPhan (IDCanBo, IDHocPhan, ThoiGian) VALUES (?, ?, ?)",
                (cb_id, subject_id, systemTime)
            )
        conn.commit()
        flash("Cập nhật giảng viên cho môn học thành công.", "success")
        return redirect(url_for('khoa_subjects'))

    # Current lecturers for this subject
    current = conn.execute("""
        SELECT CanBo.ID, CanBo.Ten
        FROM CanBo_HocPhan
        JOIN CanBo ON CanBo.ID = CanBo_HocPhan.IDCanBo
        WHERE CanBo_HocPhan.IDHocPhan=?
    """, (subject_id,)).fetchall()
    
    current_ids = {row["ID"] for row in current}

    # All lecturers (including those from other departments)
    all_lecturers = conn.execute("""
        SELECT CanBo.ID, CanBo.Ten, DonVi.Ten AS Khoa
        FROM CanBo
        JOIN DonVi ON DonVi.ID = CanBo.IDKhoa
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