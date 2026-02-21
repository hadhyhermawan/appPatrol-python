from typing import Optional, List
import datetime
import decimal

from sqlalchemy import CHAR, Column, DECIMAL, Date, DateTime, Enum, Float, ForeignKey, ForeignKeyConstraint, Index, String, TIMESTAMP, Table, Text, Time, text
from sqlalchemy.dialects.mysql import BIGINT, CHAR, DOUBLE, INTEGER, LONGTEXT, SMALLINT, TINYINT, VARCHAR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass


class Barang(Base):
    __tablename__ = 'barang'

    id_barang: Mapped[int] = mapped_column(INTEGER(11), primary_key=True)
    jenis_barang: Mapped[str] = mapped_column(String(100), nullable=False)
    dari: Mapped[str] = mapped_column(String(100), nullable=False)
    untuk: Mapped[str] = mapped_column(String(100), nullable=False)
    kode_cabang: Mapped[Optional[str]] = mapped_column(VARCHAR(50))
    

    penerima: Mapped[Optional[str]] = mapped_column(String(255))
    image: Mapped[Optional[str]] = mapped_column(String(255))
    foto_keluar: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)

    barang_keluar: Mapped[list['BarangKeluar']] = relationship('BarangKeluar', back_populates='barang', cascade='all, delete-orphan')
    barang_masuk: Mapped[list['BarangMasuk']] = relationship('BarangMasuk', back_populates='barang', cascade='all, delete-orphan')


class Cabang(Base):
    __tablename__ = 'cabang'
    __table_args__ = (
        Index('cabang_kode_up3_index', 'kode_up3'),
    )

    kode_cabang: Mapped[str] = mapped_column(CHAR(3), primary_key=True)
    nama_cabang: Mapped[str] = mapped_column(String(50), nullable=False)
    alamat_cabang: Mapped[str] = mapped_column(String(100), nullable=False)
    telepon_cabang: Mapped[str] = mapped_column(String(13), nullable=False)
    lokasi_cabang: Mapped[str] = mapped_column(String(255), nullable=False)
    radius_cabang: Mapped[int] = mapped_column(SMALLINT(6), nullable=False)
    kode_up3: Mapped[Optional[str]] = mapped_column(String(50))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)

    hari_libur: Mapped[list['HariLibur']] = relationship('HariLibur', back_populates='cabang')


class Cuti(Base):
    __tablename__ = 'cuti'

    kode_cuti: Mapped[str] = mapped_column(CHAR(3), primary_key=True)
    jenis_cuti: Mapped[str] = mapped_column(String(255), nullable=False)
    jumlah_hari: Mapped[int] = mapped_column(SMALLINT(6), nullable=False)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)

    presensi_izincuti: Mapped[list['PresensiIzincuti']] = relationship('PresensiIzincuti', back_populates='cuti')


class Denda(Base):
    __tablename__ = 'denda'

    id: Mapped[int] = mapped_column(BIGINT(20), primary_key=True)
    dari: Mapped[int] = mapped_column(SMALLINT(6), nullable=False)
    sampai: Mapped[int] = mapped_column(SMALLINT(6), nullable=False)
    denda: Mapped[int] = mapped_column(INTEGER(11), nullable=False)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)


class Departemen(Base):
    __tablename__ = 'departemen'

    kode_dept: Mapped[str] = mapped_column(CHAR(3), primary_key=True)
    nama_dept: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)

    berita: Mapped[list['Berita']] = relationship('Berita', back_populates='departemen')
    karyawan: Mapped[list['Karyawan']] = relationship('Karyawan', back_populates='departemen')


class DepartmentActivityTasks(Base):
    __tablename__ = 'department_activity_tasks'
    __table_args__ = (
        Index('dept_task_created_by_idx', 'created_by'),
        Index('dept_task_dept_tanggal_idx', 'kode_dept', 'tanggal'),
        Index('dept_task_nik_tanggal_idx', 'nik', 'tanggal')
    )

    id: Mapped[int] = mapped_column(BIGINT(20), primary_key=True)
    nik: Mapped[str] = mapped_column(String(50), nullable=False)
    kode_dept: Mapped[str] = mapped_column(String(10), nullable=False)
    tanggal: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    jam_kegiatan: Mapped[datetime.time] = mapped_column(Time, nullable=False)
    jenis_kegiatan: Mapped[str] = mapped_column(String(30), nullable=False)
    foto_kegiatan: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'complete'"))
    judul_kegiatan: Mapped[Optional[str]] = mapped_column(String(150))
    keterangan: Mapped[Optional[str]] = mapped_column(Text)
    lokasi: Mapped[Optional[str]] = mapped_column(String(255))
    created_by: Mapped[Optional[int]] = mapped_column(BIGINT(20))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)


class DepartmentTaskPointMaster(Base):
    __tablename__ = 'department_task_point_master'
    __table_args__ = (
        Index('dept_task_master_scope_active_idx', 'kode_cabang', 'kode_dept', 'is_active'),
        Index('dept_task_master_scope_order_idx', 'kode_cabang', 'kode_dept', 'urutan')
    )

    id: Mapped[int] = mapped_column(BIGINT(20), primary_key=True)
    kode_cabang: Mapped[str] = mapped_column(String(20), nullable=False)
    kode_dept: Mapped[str] = mapped_column(String(10), nullable=False)
    nama_titik: Mapped[str] = mapped_column(String(150), nullable=False)
    urutan: Mapped[int] = mapped_column(INTEGER(10), nullable=False, server_default=text('1'))
    radius: Mapped[int] = mapped_column(INTEGER(10), nullable=False, server_default=text('30'))
    is_active: Mapped[int] = mapped_column(TINYINT(1), nullable=False, server_default=text('1'))
    latitude: Mapped[Optional[decimal.Decimal]] = mapped_column(DECIMAL(11, 8))
    longitude: Mapped[Optional[decimal.Decimal]] = mapped_column(DECIMAL(11, 8))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)

    department_task_points: Mapped[list['DepartmentTaskPoints']] = relationship('DepartmentTaskPoints', back_populates='department_task_point_master')


class DepartmentTaskSessions(Base):
    __tablename__ = 'department_task_sessions'
    __table_args__ = (
        Index('dept_task_session_dept_tanggal_idx', 'kode_dept', 'tanggal'),
        Index('dept_task_session_nik_tanggal_idx', 'nik', 'tanggal'),
        Index('dept_task_session_status_tanggal_idx', 'status', 'tanggal')
    )

    id: Mapped[int] = mapped_column(BIGINT(20), primary_key=True)
    nik: Mapped[str] = mapped_column(String(50), nullable=False)
    kode_dept: Mapped[str] = mapped_column(String(10), nullable=False)
    tanggal: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    jam_tugas: Mapped[datetime.time] = mapped_column(Time, nullable=False)
    status: Mapped[str] = mapped_column(Enum('active', 'complete'), nullable=False, server_default=text("'active'"))
    kode_jam_kerja: Mapped[Optional[str]] = mapped_column(String(20))
    foto_absen: Mapped[Optional[str]] = mapped_column(String(255))
    lokasi_absen: Mapped[Optional[str]] = mapped_column(String(255))
    created_by: Mapped[Optional[int]] = mapped_column(BIGINT(20))
    completed_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)

    department_task_points: Mapped[list['DepartmentTaskPoints']] = relationship('DepartmentTaskPoints', back_populates='department_task_session')


class Detailtunjangans(Base):
    __tablename__ = 'detailtunjangans'

    id: Mapped[int] = mapped_column(BIGINT(20), primary_key=True)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)


class FailedJobs(Base):
    __tablename__ = 'failed_jobs'
    __table_args__ = (
        Index('failed_jobs_uuid_unique', 'uuid', unique=True),
    )

    id: Mapped[int] = mapped_column(BIGINT(20), primary_key=True)
    uuid: Mapped[str] = mapped_column(String(255), nullable=False)
    connection: Mapped[str] = mapped_column(Text, nullable=False)
    queue: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[str] = mapped_column(LONGTEXT, nullable=False)
    exception: Mapped[str] = mapped_column(LONGTEXT, nullable=False)
    failed_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP, nullable=False, server_default=text('current_timestamp()'))


class Izin(Base):
    __tablename__ = 'izin'

    id: Mapped[int] = mapped_column(INTEGER(11), primary_key=True)
    nik: Mapped[str] = mapped_column(CHAR(18), nullable=False)
    jenis_izin: Mapped[str] = mapped_column(Enum('SAKIT', 'CUTI', 'IZIN LAIN'), nullable=False)
    tanggal_mulai: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    tanggal_selesai: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    keterangan: Mapped[Optional[str]] = mapped_column(Text)
    file_bukti: Mapped[Optional[str]] = mapped_column(String(255))
    status: Mapped[Optional[str]] = mapped_column(Enum('Menunggu', 'Disetujui', 'Ditolak'), server_default=text("'Menunggu'"))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP, server_default=text('current_timestamp()'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP, server_default=text('current_timestamp() ON UPDATE current_timestamp()'))


class Jabatan(Base):
    __tablename__ = 'jabatan'

    kode_jabatan: Mapped[str] = mapped_column(CHAR(3), primary_key=True)
    nama_jabatan: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)

    karyawan: Mapped[list['Karyawan']] = relationship('Karyawan', back_populates='jabatan')



class SetJamKerjaByDay(Base):
    __tablename__ = 'presensi_jamkerja_byday'

    nik: Mapped[str] = mapped_column(CHAR(9), ForeignKey('karyawan.nik'), primary_key=True, nullable=False)
    hari: Mapped[str] = mapped_column(String(255), primary_key=True, nullable=False)
    kode_jam_kerja: Mapped[str] = mapped_column(CHAR(4), ForeignKey('presensi_jamkerja.kode_jam_kerja'), nullable=False)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)

    karyawan: Mapped['Karyawan'] = relationship('Karyawan', back_populates='set_jam_kerja_by_day')
    jam_kerja: Mapped['PresensiJamkerja'] = relationship('PresensiJamkerja')


class SetJamKerjaByDate(Base):
    __tablename__ = 'presensi_jamkerja_bydate'

    nik: Mapped[str] = mapped_column(CHAR(9), ForeignKey('karyawan.nik'), primary_key=True, nullable=False)
    tanggal: Mapped[datetime.date] = mapped_column(Date, primary_key=True, nullable=False)
    kode_jam_kerja: Mapped[str] = mapped_column(CHAR(4), ForeignKey('presensi_jamkerja.kode_jam_kerja'), nullable=False)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)

    karyawan: Mapped['Karyawan'] = relationship('Karyawan', back_populates='set_jam_kerja_by_date')
    jam_kerja: Mapped['PresensiJamkerja'] = relationship('PresensiJamkerja')


class JenisTunjangan(Base):
    __tablename__ = 'jenis_tunjangan'

    kode_jenis_tunjangan: Mapped[str] = mapped_column(CHAR(4), primary_key=True)
    jenis_tunjangan: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)


class Jobs(Base):
    __tablename__ = 'jobs'
    __table_args__ = (
        Index('jobs_queue_index', 'queue'),
    )

    id: Mapped[int] = mapped_column(BIGINT(20), primary_key=True)
    queue: Mapped[str] = mapped_column(String(255), nullable=False)
    payload: Mapped[str] = mapped_column(LONGTEXT, nullable=False)
    attempts: Mapped[int] = mapped_column(TINYINT(3), nullable=False)
    available_at: Mapped[int] = mapped_column(INTEGER(10), nullable=False)
    created_at: Mapped[int] = mapped_column(INTEGER(10), nullable=False)
    reserved_at: Mapped[Optional[int]] = mapped_column(INTEGER(10))






class KaryawanBpjsKesehatan(Base):
    __tablename__ = 'karyawan_bpjskesehatan'
    __table_args__ = (
        Index('karyawan_bpjskesehatan_nik_foreign', 'nik'),
    )

    kode_bpjs_kesehatan: Mapped[str] = mapped_column(CHAR(7), primary_key=True)
    nik: Mapped[str] = mapped_column(CHAR(18), nullable=False)
    jumlah: Mapped[int] = mapped_column(INTEGER(11), nullable=False)
    tanggal_berlaku: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    
    karyawan: Mapped['Karyawan'] = relationship('Karyawan', foreign_keys=[nik], primaryjoin="KaryawanBpjsKesehatan.nik == Karyawan.nik")


class KaryawanBpjstenagakerja(Base):
    __tablename__ = 'karyawan_bpjstenagakerja'
    __table_args__ = (
        Index('karyawan_bpjstenagakerja_nik_foreign', 'nik'),
    )

    kode_bpjs_tk: Mapped[str] = mapped_column(CHAR(7), primary_key=True)
    nik: Mapped[str] = mapped_column(CHAR(18), nullable=False)
    jumlah: Mapped[int] = mapped_column(INTEGER(11), nullable=False)
    tanggal_berlaku: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    
    karyawan: Mapped['Karyawan'] = relationship('Karyawan', foreign_keys=[nik], primaryjoin="KaryawanBpjstenagakerja.nik == Karyawan.nik")


class KaryawanGajiPokok(Base):
    __tablename__ = 'karyawan_gaji_pokok'
    __table_args__ = (
        Index('karyawan_gaji_pokok_nik_foreign', 'nik'),
    )

    kode_gaji: Mapped[str] = mapped_column(CHAR(7), primary_key=True)
    nik: Mapped[str] = mapped_column(CHAR(18), nullable=False)
    jumlah: Mapped[int] = mapped_column(INTEGER(11), nullable=False)
    tanggal_berlaku: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)

    karyawan: Mapped['Karyawan'] = relationship('Karyawan', foreign_keys=[nik], primaryjoin="KaryawanGajiPokok.nik == Karyawan.nik")


class KaryawanPenyesuaianGaji(Base):
    __tablename__ = 'karyawan_penyesuaian_gaji'

    kode_penyesuaian_gaji: Mapped[str] = mapped_column(CHAR(9), primary_key=True)
    bulan: Mapped[int] = mapped_column(SMALLINT(6), nullable=False)
    tahun: Mapped[int] = mapped_column(SMALLINT(6), nullable=False)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)

    details: Mapped[List['KaryawanPenyesuaianGajiDetail']] = relationship('KaryawanPenyesuaianGajiDetail', back_populates='penyesuaian_gaji', cascade="all, delete-orphan")


class KaryawanPenyesuaianGajiDetail(Base):
    __tablename__ = 'karyawan_penyesuaian_gaji_detail'
    __table_args__ = (
        Index('karyawan_penyesuaian_gaji_detail_nik_foreign', 'nik'),
        Index('karyawan_penyesuaian_gaji_detail_kode_penyesuaian_gaji_foreign', 'kode_penyesuaian_gaji'),
    )

    kode_penyesuaian_gaji: Mapped[str] = mapped_column(CHAR(9), ForeignKey('karyawan_penyesuaian_gaji.kode_penyesuaian_gaji'), primary_key=True)
    nik: Mapped[str] = mapped_column(CHAR(18), primary_key=True)
    penambah: Mapped[int] = mapped_column(INTEGER(11), nullable=False, default=0)
    pengurang: Mapped[int] = mapped_column(INTEGER(11), nullable=False, default=0)
    keterangan: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)

    penyesuaian_gaji: Mapped['KaryawanPenyesuaianGaji'] = relationship('KaryawanPenyesuaianGaji', back_populates='details')
    karyawan: Mapped['Karyawan'] = relationship('Karyawan', foreign_keys=[nik], primaryjoin="KaryawanPenyesuaianGajiDetail.nik == Karyawan.nik")


class KaryawanTunjangan(Base):
    __tablename__ = 'karyawan_tunjangan'
    __table_args__ = (
        Index('karyawan_tunjangan_nik_foreign', 'nik'),
    )

    kode_tunjangan: Mapped[str] = mapped_column(CHAR(7), primary_key=True)
    nik: Mapped[str] = mapped_column(CHAR(18), nullable=False)
    tanggal_berlaku: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)

    karyawan: Mapped['Karyawan'] = relationship('Karyawan', foreign_keys=[nik], primaryjoin="KaryawanTunjangan.nik == Karyawan.nik")
    details: Mapped[List['KaryawanTunjanganDetail']] = relationship('KaryawanTunjanganDetail', back_populates='tunjangan', cascade="all, delete-orphan")

class KaryawanTunjanganDetail(Base):
    __tablename__ = 'karyawan_tunjangan_detail'
    
    kode_tunjangan: Mapped[str] = mapped_column(CHAR(7), ForeignKey('karyawan_tunjangan.kode_tunjangan'), primary_key=True)
    kode_jenis_tunjangan: Mapped[str] = mapped_column(CHAR(4), ForeignKey('jenis_tunjangan.kode_jenis_tunjangan'), primary_key=True)
    jumlah: Mapped[int] = mapped_column(INTEGER(11), nullable=False)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    
    tunjangan: Mapped['KaryawanTunjangan'] = relationship('KaryawanTunjangan', back_populates='details')
    jenis_tunjangan: Mapped['JenisTunjangan'] = relationship('JenisTunjangan')


class KaryawanWajah(Base):
    __tablename__ = 'karyawan_wajah'
    __table_args__ = (
        Index('karyawan_wajah_nik_foreign', 'nik'),
    )

    id: Mapped[int] = mapped_column(BIGINT(20), primary_key=True)
    nik: Mapped[str] = mapped_column(CHAR(18), nullable=False)
    wajah: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)


class LandingPageSettings(Base):
    __tablename__ = 'landing_page_settings'

    id: Mapped[int] = mapped_column(BIGINT(20), primary_key=True)
    hero_pill: Mapped[Optional[str]] = mapped_column(String(255))
    hero_title: Mapped[Optional[str]] = mapped_column(String(255))
    hero_subtitle: Mapped[Optional[str]] = mapped_column(Text)
    hero_stats: Mapped[Optional[str]] = mapped_column(LONGTEXT)
    about_title: Mapped[Optional[str]] = mapped_column(String(255))
    about_body: Mapped[Optional[str]] = mapped_column(Text)
    about_card_one_title: Mapped[Optional[str]] = mapped_column(String(255))
    about_card_one_body: Mapped[Optional[str]] = mapped_column(Text)
    about_card_two_title: Mapped[Optional[str]] = mapped_column(String(255))
    about_card_two_body: Mapped[Optional[str]] = mapped_column(Text)
    services: Mapped[Optional[str]] = mapped_column(LONGTEXT)
    features: Mapped[Optional[str]] = mapped_column(LONGTEXT)
    feature_highlight_title: Mapped[Optional[str]] = mapped_column(String(255))
    feature_highlight_body: Mapped[Optional[str]] = mapped_column(Text)
    partners: Mapped[Optional[str]] = mapped_column(LONGTEXT)
    testimonials: Mapped[Optional[str]] = mapped_column(LONGTEXT)
    cta_title: Mapped[Optional[str]] = mapped_column(String(255))
    cta_body: Mapped[Optional[str]] = mapped_column(Text)
    contact_company: Mapped[Optional[str]] = mapped_column(String(255))
    contact_email: Mapped[Optional[str]] = mapped_column(String(255))
    contact_phone: Mapped[Optional[str]] = mapped_column(String(255))
    contact_address: Mapped[Optional[str]] = mapped_column(String(255))
    contact_hours: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    seo_title: Mapped[Optional[str]] = mapped_column(String(160))
    seo_description: Mapped[Optional[str]] = mapped_column(String(255))
    seo_keywords: Mapped[Optional[str]] = mapped_column(String(255))
    seo_og_image: Mapped[Optional[str]] = mapped_column(String(255))


t_laporan_barang = Table(
    'laporan_barang', Base.metadata,
    Column('id_barang', INTEGER(11), server_default=text("'0'")),
    Column('kode_cabang', CHAR(3)),
    Column('Jenis Barang', String(100)),
    Column('Dari', String(100)),
    Column('Untuk', String(100)),
    Column('Tgl Jam Masuk', DateTime),
    Column('Tgl Jam Ambil', DateTime),
    Column('foto_masuk', String(255)),
    Column('foto_keluar', String(255))
)


class Lembur(Base):
    __tablename__ = 'lembur'

    id: Mapped[int] = mapped_column(BIGINT(20), primary_key=True)
    tanggal: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    nik: Mapped[str] = mapped_column(CHAR(18), nullable=False)
    lembur_mulai: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    lembur_selesai: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(CHAR(1), nullable=False)
    keterangan: Mapped[str] = mapped_column(String(255), nullable=False)
    lembur_in: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    lembur_out: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    foto_lembur_in: Mapped[Optional[str]] = mapped_column(String(255))
    foto_lembur_out: Mapped[Optional[str]] = mapped_column(String(255))
    lokasi_lembur_in: Mapped[Optional[str]] = mapped_column(String(255))
    lokasi_lembur_out: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)


class MasterKendaraan(Base):
    __tablename__ = 'master_kendaraan'
    __table_args__ = (
        Index('master_kendaraan_plat_nomor_unique', 'plat_nomor', unique=True),
    )

    id: Mapped[int] = mapped_column(BIGINT(20), primary_key=True)
    nama_kendaraan: Mapped[str] = mapped_column(String(255), nullable=False)
    plat_nomor: Mapped[str] = mapped_column(String(255), nullable=False)
    jenis: Mapped[str] = mapped_column(Enum('BBM', 'EV'), nullable=False)
    status: Mapped[str] = mapped_column(String(255), nullable=False, server_default=text("'AVAILABLE'"))
    odometer_terakhir: Mapped[int] = mapped_column(INTEGER(11), nullable=False, server_default=text('0'))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)

    driver_p2h: Mapped[list['DriverP2h']] = relationship('DriverP2h', back_populates='kendaraan')


class Migrations(Base):
    __tablename__ = 'migrations'

    id: Mapped[int] = mapped_column(INTEGER(10), primary_key=True)
    migration: Mapped[str] = mapped_column(String(255), nullable=False)
    batch: Mapped[int] = mapped_column(INTEGER(11), nullable=False)


class PasswordResetTokens(Base):
    __tablename__ = 'password_reset_tokens'

    email: Mapped[str] = mapped_column(String(255), primary_key=True)
    token: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)


class Patrol(Base):
    __tablename__ = 'patrol'
    __table_args__ = (
        Index('patrol_unique', 'nik', 'tanggal', 'kode_jam_kerja', unique=True),
    )

    id: Mapped[int] = mapped_column(BIGINT(20), primary_key=True)
    tanggal: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    nik: Mapped[Optional[str]] = mapped_column(CHAR(18))
    foto_patrol: Mapped[Optional[str]] = mapped_column(String(255))
    loc_patrol: Mapped[Optional[str]] = mapped_column(Text)
    jam_patrol: Mapped[Optional[datetime.time]] = mapped_column(Time)
    parkir_motor: Mapped[Optional[str]] = mapped_column(String(255))
    loc_motor: Mapped[Optional[str]] = mapped_column(Text)
    jam_motor: Mapped[Optional[datetime.time]] = mapped_column(Time)
    parkir_mobil: Mapped[Optional[str]] = mapped_column(String(255))
    loc_mobil: Mapped[Optional[str]] = mapped_column(Text)
    jam_mobil: Mapped[Optional[datetime.time]] = mapped_column(Time)
    halaman_depan: Mapped[Optional[str]] = mapped_column(String(255))
    loc_depan: Mapped[Optional[str]] = mapped_column(Text)
    jam_depan: Mapped[Optional[datetime.time]] = mapped_column(Time)
    halaman_belakang: Mapped[Optional[str]] = mapped_column(String(255))
    loc_belakang: Mapped[Optional[str]] = mapped_column(Text)
    jam_belakang: Mapped[Optional[datetime.time]] = mapped_column(Time)
    gedung_satu: Mapped[Optional[str]] = mapped_column(String(255))
    loc_satu: Mapped[Optional[str]] = mapped_column(Text)
    jam_satu: Mapped[Optional[datetime.time]] = mapped_column(Time)
    gedung_dua: Mapped[Optional[str]] = mapped_column(String(255))
    loc_dua: Mapped[Optional[str]] = mapped_column(Text)
    jam_dua: Mapped[Optional[datetime.time]] = mapped_column(Time)
    blank_spot: Mapped[Optional[str]] = mapped_column(String(255))
    jam_blank: Mapped[Optional[datetime.time]] = mapped_column(Time)
    loc_blank: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[Optional[str]] = mapped_column(CHAR(4))
    kode_jam_kerja: Mapped[Optional[str]] = mapped_column(CHAR(4))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)


class PatrolPointMaster(Base):
    __tablename__ = 'patrol_point_master'
    __table_args__ = (
        Index('uk_cabang_titik', 'kode_cabang', 'nama_titik', unique=True),
    )

    id: Mapped[int] = mapped_column(BIGINT(20), primary_key=True)
    kode_cabang: Mapped[str] = mapped_column(String(50), nullable=False)
    nama_titik: Mapped[str] = mapped_column(String(255), nullable=False)
    latitude: Mapped[decimal.Decimal] = mapped_column(DECIMAL(10, 7), nullable=False)
    longitude: Mapped[decimal.Decimal] = mapped_column(DECIMAL(10, 7), nullable=False)
    radius: Mapped[int] = mapped_column(INTEGER(10), nullable=False, server_default=text('30'))
    urutan: Mapped[Optional[int]] = mapped_column(INTEGER(10), server_default=text('0'))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP, server_default=text('current_timestamp()'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP, server_default=text('current_timestamp() ON UPDATE current_timestamp()'))

    patrol_points: Mapped[list['PatrolPoints']] = relationship('PatrolPoints', back_populates='patrol_point_master')


class PatrolSchedules(Base):
    __tablename__ = 'patrol_schedules'
    __table_args__ = (
        Index('patrol_schedules_kode_jam_kerja_index', 'kode_jam_kerja'),
    )

    id: Mapped[int] = mapped_column(BIGINT(20), primary_key=True)
    kode_jam_kerja: Mapped[str] = mapped_column(String(10), nullable=False)
    start_time: Mapped[datetime.time] = mapped_column(Time, nullable=False)
    end_time: Mapped[datetime.time] = mapped_column(Time, nullable=False)
    is_active: Mapped[int] = mapped_column(TINYINT(1), nullable=False, server_default=text('1'))
    kode_dept: Mapped[Optional[str]] = mapped_column(String(10))
    kode_cabang: Mapped[Optional[str]] = mapped_column(String(10))
    name: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)


class PatrolSessions(Base):
    __tablename__ = 'patrol_sessions'
    __table_args__ = (
        Index('patrol_sessions_nik_tanggal_index', 'nik', 'tanggal'),
    )

    id: Mapped[int] = mapped_column(BIGINT(20), primary_key=True)
    nik: Mapped[str] = mapped_column(String(255), nullable=False)
    tanggal: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    kode_jam_kerja: Mapped[str] = mapped_column(String(4), nullable=False)
    jam_patrol: Mapped[datetime.time] = mapped_column(Time, nullable=False)
    status: Mapped[str] = mapped_column(Enum('active', 'complete'), nullable=False, server_default=text("'active'"))
    foto_absen: Mapped[Optional[str]] = mapped_column(String(255))
    lokasi_absen: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)

    patrol_points: Mapped[list['PatrolPoints']] = relationship('PatrolPoints', back_populates='patrol_session', cascade="all, delete-orphan")


class PengaturanUmum(Base):
    __tablename__ = 'pengaturan_umum'

    id: Mapped[int] = mapped_column(BIGINT(20), primary_key=True)
    nama_perusahaan: Mapped[str] = mapped_column(String(255), nullable=False)
    alamat: Mapped[str] = mapped_column(String(255), nullable=False)
    telepon: Mapped[str] = mapped_column(String(255), nullable=False)
    logo: Mapped[str] = mapped_column(String(255), nullable=False)
    total_jam_bulan: Mapped[int] = mapped_column(INTEGER(11), nullable=False)
    denda: Mapped[int] = mapped_column(TINYINT(1), nullable=False, server_default=text('1'))
    face_recognition: Mapped[int] = mapped_column(TINYINT(1), nullable=False, server_default=text('0'))
    periode_laporan_dari: Mapped[int] = mapped_column(SMALLINT(6), nullable=False)
    periode_laporan_sampai: Mapped[int] = mapped_column(SMALLINT(6), nullable=False)
    periode_laporan_next_bulan: Mapped[int] = mapped_column(TINYINT(1), nullable=False)
    wa_api_key: Mapped[str] = mapped_column(String(255), nullable=False)
    batasi_absen: Mapped[int] = mapped_column(TINYINT(1), nullable=False, server_default=text('0'))
    batas_jam_absen: Mapped[int] = mapped_column(SMALLINT(6), nullable=False, server_default=text('0'))
    batas_jam_absen_pulang: Mapped[int] = mapped_column(SMALLINT(6), nullable=False, server_default=text('0'))
    multi_lokasi: Mapped[int] = mapped_column(TINYINT(1), nullable=False, server_default=text('0'))
    notifikasi_wa: Mapped[int] = mapped_column(TINYINT(1), nullable=False, server_default=text('0'))
    batasi_hari_izin: Mapped[int] = mapped_column(TINYINT(1), nullable=False, server_default=text('1'))
    jml_hari_izin_max: Mapped[int] = mapped_column(INTEGER(11), nullable=False)
    batas_presensi_lintashari: Mapped[datetime.time] = mapped_column(Time, nullable=False, server_default=text("'08:00:00'"))
    toleransi_shift_malam_mulai: Mapped[datetime.time] = mapped_column(Time, nullable=False, server_default=text("'20:00:00'"))
    toleransi_shift_malam_batas: Mapped[datetime.time] = mapped_column(Time, nullable=False, server_default=text("'06:00:00'"))
    enable_face_block_system: Mapped[int] = mapped_column(TINYINT(1), nullable=False, server_default=text('1'))
    face_block_limit: Mapped[int] = mapped_column(INTEGER(11), nullable=False, server_default=text('3'))
    face_check_liveness_limit: Mapped[int] = mapped_column(INTEGER(11), nullable=False, server_default=text('3'))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    cloud_id: Mapped[Optional[str]] = mapped_column(String(255))
    api_key: Mapped[Optional[str]] = mapped_column(String(255))
    domain_email: Mapped[Optional[str]] = mapped_column(String(255))
    domain_wa_gateway: Mapped[Optional[str]] = mapped_column(String(255))
    min_supported_version_code: Mapped[Optional[int]] = mapped_column(INTEGER(11))
    latest_version_code: Mapped[Optional[int]] = mapped_column(INTEGER(11))
    update_url: Mapped[Optional[str]] = mapped_column(String(255))
    update_message: Mapped[Optional[str]] = mapped_column(Text)


class PermissionGroups(Base):
    __tablename__ = 'permission_groups'

    id: Mapped[int] = mapped_column(BIGINT(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)

    permissions: Mapped[list['Permissions']] = relationship('Permissions', back_populates='permission_groups')


class PersonalAccessTokens(Base):
    __tablename__ = 'personal_access_tokens'
    __table_args__ = (
        Index('personal_access_tokens_token_unique', 'token', unique=True),
        Index('personal_access_tokens_tokenable_type_tokenable_id_index', 'tokenable_type', 'tokenable_id')
    )

    id: Mapped[int] = mapped_column(BIGINT(20), primary_key=True)
    tokenable_type: Mapped[str] = mapped_column(String(255), nullable=False)
    tokenable_id: Mapped[int] = mapped_column(BIGINT(20), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    token: Mapped[str] = mapped_column(String(64), nullable=False)
    abilities: Mapped[Optional[str]] = mapped_column(Text)
    last_used_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    expires_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)


class PresensiIzinabsen(Base):
    __tablename__ = 'presensi_izinabsen'
    __table_args__ = (
        Index('presensi_izinabsen_nik_foreign', 'nik'),
    )

    kode_izin: Mapped[str] = mapped_column(CHAR(255), primary_key=True)
    tanggal: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    dari: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    sampai: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    nik: Mapped[str] = mapped_column(CHAR(18), nullable=False)
    keterangan: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(CHAR(1), nullable=False)
    keterangan_hrd: Mapped[Optional[str]] = mapped_column(String(255))
    foto_bukti: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)

    presensi_izinabsen_approve: Mapped[list['PresensiIzinabsenApprove']] = relationship('PresensiIzinabsenApprove', back_populates='presensi_izinabsen')


class PresensiIzindinas(Base):
    __tablename__ = 'presensi_izindinas'
    __table_args__ = (
        Index('presensi_izindinas_nik_foreign', 'nik'),
    )

    kode_izin_dinas: Mapped[str] = mapped_column(CHAR(255), primary_key=True)
    tanggal: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    dari: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    sampai: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    nik: Mapped[str] = mapped_column(CHAR(18), nullable=False)
    keterangan: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(CHAR(1), nullable=False)
    keterangan_hrd: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)


class PresensiIzinsakit(Base):
    __tablename__ = 'presensi_izinsakit'
    __table_args__ = (
        Index('presensi_izinsakit_nik_foreign', 'nik'),
    )

    kode_izin_sakit: Mapped[str] = mapped_column(CHAR(12), primary_key=True)
    nik: Mapped[str] = mapped_column(CHAR(18), nullable=False)
    tanggal: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    dari: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    sampai: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    keterangan: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(CHAR(1), nullable=False)
    id_user: Mapped[int] = mapped_column(BIGINT(20), nullable=False)
    doc_sid: Mapped[Optional[str]] = mapped_column(String(255))
    keterangan_hrd: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)

    presensi_izinsakit_approve: Mapped[list['PresensiIzinsakitApprove']] = relationship('PresensiIzinsakitApprove', back_populates='presensi_izinsakit')


class PresensiJamkerja(Base):
    __tablename__ = 'presensi_jamkerja'

    kode_jam_kerja: Mapped[str] = mapped_column(CHAR(4), primary_key=True)
    nama_jam_kerja: Mapped[str] = mapped_column(String(255), nullable=False)
    jam_masuk: Mapped[datetime.time] = mapped_column(Time, nullable=False)
    jam_pulang: Mapped[datetime.time] = mapped_column(Time, nullable=False)
    istirahat: Mapped[str] = mapped_column(CHAR(1), nullable=False)
    total_jam: Mapped[int] = mapped_column(SMALLINT(6), nullable=False)
    lintashari: Mapped[str] = mapped_column(CHAR(1), nullable=False)
    jam_awal_istirahat: Mapped[Optional[datetime.time]] = mapped_column(Time)
    jam_akhir_istirahat: Mapped[Optional[datetime.time]] = mapped_column(Time)
    keterangan: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)

    presensi: Mapped[list['Presensi']] = relationship('Presensi', back_populates='presensi_jamkerja')
    presensi_jamkerja_bydate_extra: Mapped[list['PresensiJamkerjaBydateExtra']] = relationship('PresensiJamkerjaBydateExtra', back_populates='presensi_jamkerja')





class PresensiJamkerjaBydept(Base):
    __tablename__ = 'presensi_jamkerja_bydept'

    kode_jk_dept: Mapped[str] = mapped_column(CHAR(7), primary_key=True)
    kode_cabang: Mapped[str] = mapped_column(CHAR(3), nullable=False)
    kode_dept: Mapped[str] = mapped_column(CHAR(3), nullable=False)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    



class PresensiJamkerjaBydeptDetail(Base):
    __tablename__ = 'presensi_jamkerja_bydept_detail'

    kode_jk_dept: Mapped[str] = mapped_column(CHAR(7), primary_key=True, nullable=False)
    hari: Mapped[str] = mapped_column(String(20), primary_key=True, nullable=False)
    kode_jam_kerja: Mapped[str] = mapped_column(CHAR(4), nullable=False)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)




class Roles(Base):
    __tablename__ = 'roles'
    __table_args__ = (
        Index('roles_name_guard_name_unique', 'name', 'guard_name', unique=True),
    )

    id: Mapped[int] = mapped_column(BIGINT(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    guard_name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)

    model_has_roles: Mapped[list['ModelHasRoles']] = relationship('ModelHasRoles', back_populates='role')
    permission: Mapped[list['Permissions']] = relationship('Permissions', secondary='role_has_permissions', back_populates='role')


class Sessions(Base):
    __tablename__ = 'sessions'
    __table_args__ = (
        Index('sessions_last_activity_index', 'last_activity'),
        Index('sessions_user_id_index', 'user_id')
    )

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    payload: Mapped[str] = mapped_column(LONGTEXT, nullable=False)
    last_activity: Mapped[int] = mapped_column(INTEGER(11), nullable=False)
    user_id: Mapped[Optional[int]] = mapped_column(BIGINT(20))
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    user_agent: Mapped[Optional[str]] = mapped_column(Text)





class StatusKawin(Base):
    __tablename__ = 'status_kawin'

    kode_status_kawin: Mapped[str] = mapped_column(CHAR(2), primary_key=True)
    status_kawin: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)


class Users(Base):
    __tablename__ = 'users'
    __table_args__ = (
        Index('users_email_unique', 'email', unique=True),
    )

    id: Mapped[int] = mapped_column(BIGINT(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    username: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(20))
    address: Mapped[Optional[str]] = mapped_column(Text)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    foto: Mapped[Optional[str]] = mapped_column(String(255))
    email_verified_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    remember_token: Mapped[Optional[str]] = mapped_column(String(100))

    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)

    berita: Mapped[list['Berita']] = relationship('Berita', back_populates='users')
    driver_p2h: Mapped[list['DriverP2h']] = relationship('DriverP2h', back_populates='user', passive_deletes=True)
    login_log_device_ignores: Mapped[list['LoginLogDeviceIgnores']] = relationship('LoginLogDeviceIgnores', foreign_keys='[LoginLogDeviceIgnores.created_by]', back_populates='users', passive_deletes=True)
    login_log_device_ignores_: Mapped[list['LoginLogDeviceIgnores']] = relationship('LoginLogDeviceIgnores', foreign_keys='[LoginLogDeviceIgnores.user_id]', back_populates='user', passive_deletes=True)
    login_logs: Mapped[list['LoginLogs']] = relationship('LoginLogs', back_populates='user', passive_deletes=True)
    security_reports: Mapped[list['SecurityReports']] = relationship('SecurityReports', back_populates='user')
    driver_job_orders: Mapped[list['DriverJobOrders']] = relationship('DriverJobOrders', back_populates='user', passive_deletes=True)
    emergency_alerts: Mapped[list['EmergencyAlerts']] = relationship('EmergencyAlerts', back_populates='users', passive_deletes=True)
    presensi_jamkerja_bydate_extra: Mapped[list['PresensiJamkerjaBydateExtra']] = relationship('PresensiJamkerjaBydateExtra', back_populates='users')


class Userkaryawan(Base):
    __tablename__ = 'users_karyawan'
    __table_args__ = (
        Index('users_karyawan_nik_foreign', 'nik'),
    )

    nik: Mapped[str] = mapped_column(CHAR(18), primary_key=True)
    id_user: Mapped[int] = mapped_column(BIGINT(20), primary_key=True)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)


class WalkieChannels(Base):
    __tablename__ = 'walkie_channels'
    __table_args__ = (
        Index('walkie_channels_code_unique', 'code', unique=True),
    )

    id: Mapped[int] = mapped_column(BIGINT(20), primary_key=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    rule_type: Mapped[str] = mapped_column(String(32), nullable=False)
    rule_value: Mapped[str] = mapped_column(String(255), nullable=False)
    active: Mapped[int] = mapped_column(TINYINT(1), nullable=False, server_default=text('1'))
    auto_join: Mapped[int] = mapped_column(TINYINT(1), nullable=False, server_default=text('1'))
    priority: Mapped[int] = mapped_column(INTEGER(10), nullable=False, server_default=text('100'))
    dept_members: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)

    walkie_channel_cabangs: Mapped[list['WalkieChannelCabangs']] = relationship('WalkieChannelCabangs', back_populates='walkie_channel')


class WalkieRtcLogs(Base):
    __tablename__ = 'walkie_rtc_logs'

    id: Mapped[int] = mapped_column(BIGINT(20), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(50), nullable=False)
    nama: Mapped[str] = mapped_column(String(150), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    branch: Mapped[str] = mapped_column(String(50), nullable=False)
    message_type: Mapped[str] = mapped_column(Enum('ptt_start', 'ptt_end'), nullable=False)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP, server_default=text('current_timestamp()'))


class WalkieRtcMessages(Base):
    __tablename__ = 'walkie_rtc_messages'

    id: Mapped[int] = mapped_column(BIGINT(20), primary_key=True)
    room: Mapped[str] = mapped_column(String(50), nullable=False)
    sender_nama: Mapped[str] = mapped_column(String(150), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    sender_id: Mapped[Optional[str]] = mapped_column(CHAR(18))
    attachment: Mapped[Optional[str]] = mapped_column(String(255))
    attachment_type: Mapped[Optional[str]] = mapped_column(String(255))
    reply_to: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP, server_default=text('current_timestamp()'))


class Wamessages(Base):
    __tablename__ = 'wamessages'

    id: Mapped[int] = mapped_column(BIGINT(20), primary_key=True)
    sender: Mapped[str] = mapped_column(String(255), nullable=False)
    receiver: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[int] = mapped_column(TINYINT(1), nullable=False, server_default=text('0'))
    sent_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP, nullable=False, server_default=text("'2025-06-10 16:26:41'"))
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)


class Berita(Base):
    __tablename__ = 'berita'
    __table_args__ = (
        ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL', name='berita_created_by_foreign'),
        ForeignKeyConstraint(['kode_dept_target'], ['departemen.kode_dept'], ondelete='SET NULL', onupdate='CASCADE', name='berita_kode_dept_target_foreign'),
        Index('berita_created_by_foreign', 'created_by'),
        Index('berita_kode_dept_target_index', 'kode_dept_target')
    )

    id: Mapped[int] = mapped_column(BIGINT(20), primary_key=True)
    judul: Mapped[str] = mapped_column(String(255), nullable=False)
    isi: Mapped[str] = mapped_column(Text, nullable=False)
    foto: Mapped[Optional[str]] = mapped_column(String(255))
    kode_dept_target: Mapped[Optional[str]] = mapped_column(CHAR(3))
    created_by: Mapped[Optional[int]] = mapped_column(BIGINT(20))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)

    users: Mapped[Optional['Users']] = relationship('Users', back_populates='berita')
    departemen: Mapped[Optional['Departemen']] = relationship('Departemen', back_populates='berita')


class DepartmentTaskPoints(Base):
    __tablename__ = 'department_task_points'
    __table_args__ = (
        ForeignKeyConstraint(['department_task_point_master_id'], ['department_task_point_master.id'], ondelete='CASCADE', name='dept_task_points_master_fk'),
        ForeignKeyConstraint(['department_task_session_id'], ['department_task_sessions.id'], ondelete='CASCADE', name='dept_task_points_session_fk'),
        Index('dept_task_points_master_fk', 'department_task_point_master_id'),
        Index('dept_task_points_session_jam_idx', 'department_task_session_id', 'jam'),
        Index('dept_task_points_unique_session_master', 'department_task_session_id', 'department_task_point_master_id', unique=True)
    )

    id: Mapped[int] = mapped_column(BIGINT(20), primary_key=True)
    department_task_session_id: Mapped[int] = mapped_column(BIGINT(20), nullable=False)
    department_task_point_master_id: Mapped[int] = mapped_column(BIGINT(20), nullable=False)
    foto: Mapped[Optional[str]] = mapped_column(String(255))
    lokasi: Mapped[Optional[str]] = mapped_column(String(255))
    jam: Mapped[Optional[datetime.time]] = mapped_column(Time)
    keterangan: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)

    department_task_point_master: Mapped['DepartmentTaskPointMaster'] = relationship('DepartmentTaskPointMaster', back_populates='department_task_points')
    department_task_session: Mapped['DepartmentTaskSessions'] = relationship('DepartmentTaskSessions', back_populates='department_task_points')


class DriverP2h(Base):
    __tablename__ = 'driver_p2h'
    __table_args__ = (
        ForeignKeyConstraint(['kendaraan_id'], ['master_kendaraan.id'], name='driver_p2h_kendaraan_id_foreign'),
        ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE', name='driver_p2h_user_id_foreign'),
        Index('driver_p2h_kendaraan_id_foreign', 'kendaraan_id'),
        Index('driver_p2h_user_id_foreign', 'user_id')
    )

    id: Mapped[int] = mapped_column(BIGINT(20), primary_key=True)
    user_id: Mapped[int] = mapped_column(BIGINT(20), nullable=False)
    kendaraan_id: Mapped[int] = mapped_column(BIGINT(20), nullable=False)
    tanggal: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    odometer_awal: Mapped[int] = mapped_column(INTEGER(11), nullable=False)
    status_p2h: Mapped[str] = mapped_column(Enum('PENDING', 'APPROVED', 'REJECTED'), nullable=False, server_default=text("'PENDING'"))
    checklist_fisik: Mapped[Optional[str]] = mapped_column(Text)
    energi_awal_level: Mapped[Optional[str]] = mapped_column(String(255))
    sisa_jarak_estimasi: Mapped[Optional[int]] = mapped_column(INTEGER(11))
    foto_kendaraan_depan: Mapped[Optional[str]] = mapped_column(String(255))
    foto_kendaraan_samping: Mapped[Optional[str]] = mapped_column(String(255))
    foto_odometer_awal: Mapped[Optional[str]] = mapped_column(String(255))
    catatan_driver: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)

    kendaraan: Mapped['MasterKendaraan'] = relationship('MasterKendaraan', back_populates='driver_p2h')
    user: Mapped['Users'] = relationship('Users', back_populates='driver_p2h', passive_deletes=True)
    driver_energy_logs: Mapped[list['DriverEnergyLogs']] = relationship('DriverEnergyLogs', back_populates='p2h')
    driver_job_orders: Mapped[list['DriverJobOrders']] = relationship('DriverJobOrders', back_populates='p2h')
    driver_reimbursements: Mapped[list['DriverReimbursements']] = relationship('DriverReimbursements', back_populates='p2h')


class EmployeeLocationHistories(Base):
    __tablename__ = 'employee_location_histories'
    __table_args__ = (
        ForeignKeyConstraint(['nik'], ['users_karyawan.nik'], ondelete='CASCADE', name='fk_history_karyawan'),
        Index('fk_history_karyawan', 'nik'),
        Index('idx_user_time', 'user_id', 'recorded_at')
    )

    id: Mapped[int] = mapped_column(BIGINT(20), primary_key=True)
    nik: Mapped[str] = mapped_column(CHAR(18), nullable=False)
    latitude: Mapped[decimal.Decimal] = mapped_column(DECIMAL(10, 8), nullable=False)
    longitude: Mapped[decimal.Decimal] = mapped_column(DECIMAL(11, 8), nullable=False)
    user_id: Mapped[Optional[int]] = mapped_column(BIGINT(20))
    accuracy: Mapped[Optional[float]] = mapped_column(Float)
    speed: Mapped[Optional[float]] = mapped_column(Float)
    bearing: Mapped[Optional[float]] = mapped_column(Float)
    provider: Mapped[Optional[str]] = mapped_column(String(20))
    is_mocked: Mapped[Optional[int]] = mapped_column(TINYINT(1), server_default=text('0'))
    recorded_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP, server_default=text('current_timestamp()'))


class EmployeeLocations(Base):
    __tablename__ = 'employee_locations'
    __table_args__ = (
        ForeignKeyConstraint(['nik'], ['users_karyawan.nik'], ondelete='CASCADE', name='fk_locations_karyawan'),
        Index('employee_locations_id_unique', 'id', unique=True)
    )

    id: Mapped[int] = mapped_column(BIGINT(20), nullable=False)
    nik: Mapped[str] = mapped_column(CHAR(18), primary_key=True)
    latitude: Mapped[decimal.Decimal] = mapped_column(DECIMAL(10, 8), nullable=False)
    longitude: Mapped[decimal.Decimal] = mapped_column(DECIMAL(11, 8), nullable=False)
    user_id: Mapped[Optional[int]] = mapped_column(BIGINT(20))
    accuracy: Mapped[Optional[float]] = mapped_column(Float)
    speed: Mapped[Optional[float]] = mapped_column(Float)
    bearing: Mapped[Optional[float]] = mapped_column(Float)
    provider: Mapped[Optional[str]] = mapped_column(String(20), server_default=text("'gps'"))
    is_mocked: Mapped[Optional[int]] = mapped_column(TINYINT(1), server_default=text('0'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP, server_default=text('current_timestamp() ON UPDATE current_timestamp()'))


class EmployeeStatus(Base):
    __tablename__ = 'employee_status'
    __table_args__ = (
        ForeignKeyConstraint(['nik'], ['users_karyawan.nik'], ondelete='CASCADE', name='fk_status_karyawan'),
        Index('idx_status_online', 'is_online')
    )

    nik: Mapped[str] = mapped_column(CHAR(18), primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(BIGINT(20))
    is_online: Mapped[Optional[int]] = mapped_column(TINYINT(1), server_default=text('0'))
    last_seen: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    battery_level: Mapped[Optional[int]] = mapped_column(INTEGER(11))
    is_charging: Mapped[Optional[int]] = mapped_column(TINYINT(1), server_default=text('0'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP, server_default=text('current_timestamp()'))


class HariLibur(Base):
    __tablename__ = 'hari_libur'
    __table_args__ = (
        ForeignKeyConstraint(['kode_cabang'], ['cabang.kode_cabang'], onupdate='CASCADE', name='hari_libur_kode_cabang_foreign'),
        Index('hari_libur_kode_cabang_foreign', 'kode_cabang')
    )

    kode_libur: Mapped[str] = mapped_column(CHAR(7), primary_key=True)
    tanggal: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    kode_cabang: Mapped[str] = mapped_column(CHAR(3), nullable=False)
    keterangan: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)

    cabang: Mapped['Cabang'] = relationship('Cabang', back_populates='hari_libur')


class Karyawan(Base):
    __tablename__ = 'karyawan'
    __table_args__ = (
        ForeignKeyConstraint(['kode_dept'], ['departemen.kode_dept'], onupdate='CASCADE', name='karyawan_kode_dept_foreign'),
        ForeignKeyConstraint(['kode_jabatan'], ['jabatan.kode_jabatan'], onupdate='CASCADE', name='karyawan_kode_jabatan_foreign'),
        Index('karyawan_kode_dept_foreign', 'kode_dept'),
        Index('karyawan_kode_jabatan_foreign', 'kode_jabatan')
    )

    nik: Mapped[str] = mapped_column(CHAR(18), primary_key=True)
    no_ktp: Mapped[str] = mapped_column(String(16), nullable=False)
    nama_karyawan: Mapped[str] = mapped_column(String(100), nullable=False)
    jenis_kelamin: Mapped[str] = mapped_column(CHAR(1), nullable=False)
    kode_cabang: Mapped[str] = mapped_column(CHAR(3), nullable=False)
    kode_dept: Mapped[str] = mapped_column(CHAR(3), nullable=False)
    kode_jabatan: Mapped[str] = mapped_column(CHAR(3), nullable=False)
    tanggal_masuk: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    status_karyawan: Mapped[str] = mapped_column(CHAR(1), nullable=False)
    lock_location: Mapped[str] = mapped_column(CHAR(1), nullable=False)
    lock_device_login: Mapped[str] = mapped_column(CHAR(1), nullable=False, server_default=text("'0'"))
    allow_multi_device: Mapped[str] = mapped_column(CHAR(1), nullable=False, server_default=text("'0'"))
    lock_jam_kerja: Mapped[str] = mapped_column(CHAR(1), nullable=False, server_default=text("'1'"))
    lock_patrol: Mapped[str] = mapped_column(CHAR(1), nullable=False, server_default=text("'1'"), comment='1 = patroli aktif, 0 = patroli nonaktif')
    status_aktif_karyawan: Mapped[str] = mapped_column(CHAR(1), nullable=False)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    tempat_lahir: Mapped[Optional[str]] = mapped_column(String(20))
    tanggal_lahir: Mapped[Optional[datetime.date]] = mapped_column(Date)
    alamat: Mapped[Optional[str]] = mapped_column(String(255))
    no_hp: Mapped[Optional[str]] = mapped_column(String(15))
    kontak_darurat_nama: Mapped[Optional[str]] = mapped_column(String(100))
    kontak_darurat_hp: Mapped[Optional[str]] = mapped_column(String(20))
    kontak_darurat_alamat: Mapped[Optional[str]] = mapped_column(String(255))
    kode_status_kawin: Mapped[Optional[str]] = mapped_column(CHAR(2))
    pendidikan_terakhir: Mapped[Optional[str]] = mapped_column(String(4))
    no_ijazah: Mapped[Optional[str]] = mapped_column(String(255))
    no_sim: Mapped[Optional[str]] = mapped_column(String(50))
    no_kartu_anggota: Mapped[Optional[str]] = mapped_column(String(100))
    foto: Mapped[Optional[str]] = mapped_column(String(255))
    foto_ktp: Mapped[Optional[str]] = mapped_column(String(255))
    foto_kartu_anggota: Mapped[Optional[str]] = mapped_column(String(255))
    foto_ijazah: Mapped[Optional[str]] = mapped_column(String(255))
    foto_sim: Mapped[Optional[str]] = mapped_column(String(255))
    kode_jadwal: Mapped[Optional[str]] = mapped_column(CHAR(5))
    pin: Mapped[Optional[int]] = mapped_column(SMALLINT(6))
    tanggal_nonaktif: Mapped[Optional[datetime.date]] = mapped_column(Date)
    tanggal_off_gaji: Mapped[Optional[datetime.date]] = mapped_column(Date)
    masa_aktif_karyawan: Mapped[Optional[datetime.date]] = mapped_column(Date)
    masa_aktif_kartu_anggota: Mapped[Optional[datetime.date]] = mapped_column(Date)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    last_activity: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)

    departemen: Mapped['Departemen'] = relationship('Departemen', back_populates='karyawan')
    jabatan: Mapped['Jabatan'] = relationship('Jabatan', back_populates='karyawan')
    barang_keluar: Mapped[list['BarangKeluar']] = relationship('BarangKeluar', back_populates='karyawan')
    barang_masuk: Mapped[list['BarangMasuk']] = relationship('BarangMasuk', back_populates='karyawan')
    emergency_alerts: Mapped[list['EmergencyAlerts']] = relationship('EmergencyAlerts', back_populates='karyawan', passive_deletes=True)
    karyawan_devices: Mapped[list['KaryawanDevices']] = relationship('KaryawanDevices', back_populates='karyawan')
    pengunjung: Mapped[list['Pengunjung']] = relationship('Pengunjung', back_populates='karyawan')
    presensi_izin: Mapped[list['PresensiIzin']] = relationship('PresensiIzin', back_populates='karyawan')
    presensi_jamkerja_bydate_extra: Mapped[list['PresensiJamkerjaBydateExtra']] = relationship('PresensiJamkerjaBydateExtra', back_populates='karyawan')
    safety_briefings: Mapped[list['SafetyBriefings']] = relationship('SafetyBriefings', back_populates='karyawan')
    surat_keluar: Mapped[list['SuratKeluar']] = relationship('SuratKeluar', back_populates='karyawan')
    surat_masuk: Mapped[list['SuratMasuk']] = relationship('SuratMasuk', back_populates='karyawan')
    tamu: Mapped[list['Tamu']] = relationship('Tamu', back_populates='karyawan')
    turlalin: Mapped[list['Turlalin']] = relationship('Turlalin', foreign_keys='[Turlalin.nik]', back_populates='karyawan')
    turlalin_: Mapped[list['Turlalin']] = relationship('Turlalin', foreign_keys='[Turlalin.nik_keluar]', back_populates='karyawan_')
    walkie_logs: Mapped[list['WalkieLogs']] = relationship('WalkieLogs', back_populates='karyawan')
    set_jam_kerja_by_day: Mapped[list['SetJamKerjaByDay']] = relationship('SetJamKerjaByDay', back_populates='karyawan')
    set_jam_kerja_by_date: Mapped[list['SetJamKerjaByDate']] = relationship('SetJamKerjaByDate', back_populates='karyawan')
    violations: Mapped[list['Violation']] = relationship('Violation', back_populates='karyawan')
    app_frauds: Mapped[list['AppFraud']] = relationship('AppFraud', back_populates='karyawan')








class LoginLogDeviceIgnores(Base):
    __tablename__ = 'login_log_device_ignores'
    __table_args__ = (
        ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL', name='login_log_device_ignores_created_by_foreign'),
        ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE', name='login_log_device_ignores_user_id_foreign'),
        Index('login_log_device_ignores_created_by_foreign', 'created_by'),
        Index('login_log_device_ignores_user_id_device_unique', 'user_id', 'device', unique=True),
        Index('login_log_device_ignores_user_id_index', 'user_id')
    )

    id: Mapped[int] = mapped_column(BIGINT(20), primary_key=True)
    user_id: Mapped[int] = mapped_column(BIGINT(20), nullable=False)
    device: Mapped[str] = mapped_column(String(255), nullable=False)
    created_by: Mapped[Optional[int]] = mapped_column(BIGINT(20))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)

    users: Mapped[Optional['Users']] = relationship('Users', foreign_keys=[created_by], back_populates='login_log_device_ignores', passive_deletes=True)
    user: Mapped['Users'] = relationship('Users', foreign_keys=[user_id], back_populates='login_log_device_ignores_', passive_deletes=True)


class LoginLogs(Base):
    __tablename__ = 'login_logs'
    __table_args__ = (
        ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE', name='login_logs_user_id_foreign'),
        Index('login_logs_user_id_foreign', 'user_id')
    )

    id: Mapped[int] = mapped_column(BIGINT(20), primary_key=True)
    user_id: Mapped[int] = mapped_column(BIGINT(20), nullable=False)
    ip: Mapped[str] = mapped_column(String(45), nullable=False)
    login_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP, nullable=False, server_default=text('current_timestamp()'))
    device: Mapped[Optional[str]] = mapped_column(String(255))
    android_version: Mapped[Optional[str]] = mapped_column(String(255), comment='Versi Android/Build yang login')
    logout_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)

    user: Mapped['Users'] = relationship('Users', back_populates='login_logs', passive_deletes=True)


class ModelHasRoles(Base):
    __tablename__ = 'model_has_roles'
    __table_args__ = (
        ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='CASCADE', name='model_has_roles_role_id_foreign'),
        Index('model_has_roles_model_id_model_type_index', 'model_id', 'model_type')
    )

    role_id: Mapped[int] = mapped_column(BIGINT(20), primary_key=True)
    model_type: Mapped[str] = mapped_column(String(255), primary_key=True)
    model_id: Mapped[int] = mapped_column(BIGINT(20), primary_key=True)

    role: Mapped['Roles'] = relationship('Roles', back_populates='model_has_roles')


class PatrolPoints(Base):
    __tablename__ = 'patrol_points'
    __table_args__ = (
        ForeignKeyConstraint(['patrol_point_master_id'], ['patrol_point_master.id'], ondelete='CASCADE', name='fk_patrol_point_master'),
        ForeignKeyConstraint(['patrol_session_id'], ['patrol_sessions.id'], ondelete='CASCADE', name='patrol_points_patrol_session_id_foreign'),
        Index('fk_patrol_point_master', 'patrol_point_master_id'),
        Index('patrol_points_patrol_session_id_foreign', 'patrol_session_id')
    )

    id: Mapped[int] = mapped_column(BIGINT(20), primary_key=True)
    patrol_session_id: Mapped[int] = mapped_column(BIGINT(20), nullable=False)
    patrol_point_master_id: Mapped[Optional[int]] = mapped_column(BIGINT(20))
    foto: Mapped[Optional[str]] = mapped_column(String(255))
    lokasi: Mapped[Optional[str]] = mapped_column(String(255))
    jam: Mapped[Optional[datetime.time]] = mapped_column(Time)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)

    patrol_point_master: Mapped[Optional['PatrolPointMaster']] = relationship('PatrolPointMaster', back_populates='patrol_points')
    patrol_session: Mapped['PatrolSessions'] = relationship('PatrolSessions', back_populates='patrol_points')


class Permissions(Base):
    __tablename__ = 'permissions'
    __table_args__ = (
        ForeignKeyConstraint(['id_permission_group'], ['permission_groups.id'], onupdate='CASCADE', name='permissions_id_permission_group_foreign'),
        Index('permissions_id_permission_group_foreign', 'id_permission_group'),
        Index('permissions_name_guard_name_unique', 'name', 'guard_name', unique=True)
    )

    id: Mapped[int] = mapped_column(BIGINT(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    guard_name: Mapped[str] = mapped_column(String(255), nullable=False)
    id_permission_group: Mapped[int] = mapped_column(BIGINT(20), nullable=False)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)

    permission_groups: Mapped['PermissionGroups'] = relationship('PermissionGroups', back_populates='permissions')
    role: Mapped[list['Roles']] = relationship('Roles', secondary='role_has_permissions', back_populates='permission')
    model_has_permissions: Mapped[list['ModelHasPermissions']] = relationship('ModelHasPermissions', back_populates='permission')


class Presensi(Base):
    __tablename__ = 'presensi'
    __table_args__ = (
        ForeignKeyConstraint(['kode_jam_kerja'], ['presensi_jamkerja.kode_jam_kerja'], onupdate='CASCADE', name='presensi_kode_jam_kerja_foreign'),
        Index('presensi_kode_jam_kerja_foreign', 'kode_jam_kerja'),
        Index('presensi_nik_foreign', 'nik'),
        Index('presensi_unique', 'nik', 'tanggal', 'kode_jam_kerja', unique=True)
    )

    id: Mapped[int] = mapped_column(BIGINT(20), primary_key=True)
    nik: Mapped[str] = mapped_column(CHAR(18), nullable=False)
    tanggal: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    kode_jam_kerja: Mapped[str] = mapped_column(CHAR(4), nullable=False)
    status: Mapped[str] = mapped_column(CHAR(1), nullable=False)
    lintashari: Mapped[int] = mapped_column(TINYINT(1), nullable=False, server_default=text('0'))
    jam_in: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    jam_out: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    foto_in: Mapped[Optional[str]] = mapped_column(String(255))
    foto_out: Mapped[Optional[str]] = mapped_column(String(255))
    lokasi_in: Mapped[Optional[str]] = mapped_column(String(255))
    lokasi_out: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    istirahat_in: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    lokasi_istirahat_in: Mapped[Optional[str]] = mapped_column(String(255))
    foto_istirahat_in: Mapped[Optional[str]] = mapped_column(String(255))
    istirahat_out: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    lokasi_istirahat_out: Mapped[Optional[str]] = mapped_column(String(255))
    foto_istirahat_out: Mapped[Optional[str]] = mapped_column(String(255))

    presensi_jamkerja: Mapped['PresensiJamkerja'] = relationship('PresensiJamkerja', back_populates='presensi')


class PresensiIzincuti(Base):
    __tablename__ = 'presensi_izincuti'
    __table_args__ = (
        ForeignKeyConstraint(['kode_cuti'], ['cuti.kode_cuti'], onupdate='CASCADE', name='presensi_izincuti_kode_cuti_foreign'),
        Index('presensi_izincuti_kode_cuti_foreign', 'kode_cuti'),
        Index('presensi_izincuti_nik_foreign', 'nik')
    )

    kode_izin_cuti: Mapped[str] = mapped_column(CHAR(12), primary_key=True)
    nik: Mapped[str] = mapped_column(CHAR(18), nullable=False)
    tanggal: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    dari: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    sampai: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    kode_cuti: Mapped[str] = mapped_column(CHAR(3), nullable=False)
    keterangan: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(CHAR(1), nullable=False)
    id_user: Mapped[int] = mapped_column(BIGINT(20), nullable=False)
    keterangan_hrd: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)

    cuti: Mapped['Cuti'] = relationship('Cuti', back_populates='presensi_izincuti')
    presensi_izincuti_approve: Mapped[list['PresensiIzincutiApprove']] = relationship('PresensiIzincutiApprove', back_populates='presensi_izincuti')





# t_presensi_jamkerja_bydept_detail replaced by ORM class



class SecurityReports(Base):
    __tablename__ = 'security_reports'
    __table_args__ = (
        ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL', name='security_reports_user_id_foreign'),
        Index('security_reports_client_token_id_index', 'client_token_id'),
        Index('security_reports_device_id_index', 'device_id'),
        Index('security_reports_nik_index', 'nik'),
        Index('security_reports_type_created_at_index', 'type', 'created_at'),
        Index('security_reports_type_index', 'type'),
        Index('security_reports_user_id_foreign', 'user_id')
    )

    id: Mapped[int] = mapped_column(BIGINT(20), primary_key=True)
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    status_flag: Mapped[str] = mapped_column(String(50), nullable=False, server_default=text("'pending'"))
    user_id: Mapped[Optional[int]] = mapped_column(BIGINT(20))
    client_token_id: Mapped[Optional[int]] = mapped_column(BIGINT(20))
    nik: Mapped[Optional[str]] = mapped_column(String(50))
    device_model: Mapped[Optional[str]] = mapped_column(String(150))
    device_id: Mapped[Optional[str]] = mapped_column(String(191))
    fail_count: Mapped[Optional[int]] = mapped_column(INTEGER(10))
    latitude: Mapped[Optional[decimal.Decimal]] = mapped_column(DECIMAL(10, 7))
    longitude: Mapped[Optional[decimal.Decimal]] = mapped_column(DECIMAL(10, 7))
    detail: Mapped[Optional[str]] = mapped_column(Text)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    user_agent: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)

    user: Mapped[Optional['Users']] = relationship('Users', back_populates='security_reports')


class WalkieChannelCabangs(Base):
    __tablename__ = 'walkie_channel_cabangs'
    __table_args__ = (
        ForeignKeyConstraint(['walkie_channel_id'], ['walkie_channels.id'], ondelete='CASCADE', name='walkie_channel_cabangs_walkie_channel_id_foreign'),
        Index('walkie_channel_cabangs_kode_cabang_index', 'kode_cabang'),
        Index('walkie_channel_cabangs_unique', 'walkie_channel_id', 'kode_cabang', unique=True)
    )

    id: Mapped[int] = mapped_column(BIGINT(20), primary_key=True)
    walkie_channel_id: Mapped[int] = mapped_column(BIGINT(20), nullable=False)
    kode_cabang: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)

    walkie_channel: Mapped['WalkieChannels'] = relationship('WalkieChannels', back_populates='walkie_channel_cabangs')


class BarangKeluar(Base):
    __tablename__ = 'barang_keluar'
    __table_args__ = (
        ForeignKeyConstraint(['id_barang'], ['barang.id_barang'], name='fk_bk_barang'),
        ForeignKeyConstraint(['nik_penyerah'], ['karyawan.nik'], name='fk_bk_penyerah'),
        Index('fk_bk_penerima', 'nama_penerima'),
        Index('fk_bk_penyerah', 'nik_penyerah'),
        Index('idx_barang_keluar_latest', 'id_barang', 'tgl_jam_keluar')
    )

    id_barang_keluar: Mapped[int] = mapped_column(INTEGER(11), primary_key=True)
    id_barang: Mapped[int] = mapped_column(INTEGER(11), nullable=False)
    nik_penyerah: Mapped[str] = mapped_column(CHAR(18), nullable=False)
    nama_penerima: Mapped[str] = mapped_column(String(255), nullable=False)
    tgl_jam_keluar: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    no_handphone: Mapped[Optional[str]] = mapped_column(String(20))

    barang: Mapped['Barang'] = relationship('Barang', back_populates='barang_keluar')
    karyawan: Mapped['Karyawan'] = relationship('Karyawan', back_populates='barang_keluar')


class BarangMasuk(Base):
    __tablename__ = 'barang_masuk'
    __table_args__ = (
        ForeignKeyConstraint(['id_barang'], ['barang.id_barang'], name='fk_bm_barang'),
        ForeignKeyConstraint(['nik_satpam'], ['karyawan.nik'], name='fk_bm_satpam'),
        Index('fk_bm_satpam', 'nik_satpam'),
        Index('idx_barang_masuk_latest', 'id_barang', 'tgl_jam_masuk')
    )

    id_barang_masuk: Mapped[int] = mapped_column(INTEGER(11), primary_key=True)
    id_barang: Mapped[int] = mapped_column(INTEGER(11), nullable=False)
    nik_satpam: Mapped[str] = mapped_column(CHAR(18), nullable=False)
    tgl_jam_masuk: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)

    barang: Mapped['Barang'] = relationship('Barang', back_populates='barang_masuk')
    karyawan: Mapped['Karyawan'] = relationship('Karyawan', back_populates='barang_masuk')


class DriverEnergyLogs(Base):
    __tablename__ = 'driver_energy_logs'
    __table_args__ = (
        ForeignKeyConstraint(['p2h_id'], ['driver_p2h.id'], name='driver_energy_logs_p2h_id_foreign'),
        Index('driver_energy_logs_p2h_id_foreign', 'p2h_id')
    )

    id: Mapped[int] = mapped_column(BIGINT(20), primary_key=True)
    p2h_id: Mapped[int] = mapped_column(BIGINT(20), nullable=False)
    jenis_energi: Mapped[str] = mapped_column(Enum('BBM', 'EV_CHARGING'), nullable=False)
    biaya: Mapped[int] = mapped_column(INTEGER(11), nullable=False, server_default=text('0'))
    jenis_bbm: Mapped[Optional[str]] = mapped_column(String(255))
    jumlah_liter: Mapped[Optional[decimal.Decimal]] = mapped_column(DOUBLE(8, 2))
    lokasi_spklu: Mapped[Optional[str]] = mapped_column(String(255))
    persen_baterai_awal: Mapped[Optional[int]] = mapped_column(INTEGER(11))
    persen_baterai_akhir: Mapped[Optional[int]] = mapped_column(INTEGER(11))
    durasi_menit: Mapped[Optional[int]] = mapped_column(INTEGER(11))
    foto_struk: Mapped[Optional[str]] = mapped_column(String(255))
    foto_odometer_saat_isi: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)

    p2h: Mapped['DriverP2h'] = relationship('DriverP2h', back_populates='driver_energy_logs')


class SlipGaji(Base):
    __tablename__ = 'slip_gaji'
    
    kode_slip_gaji: Mapped[str] = mapped_column(CHAR(8), primary_key=True)
    bulan: Mapped[int] = mapped_column(SMALLINT(6), nullable=False)
    tahun: Mapped[str] = mapped_column(CHAR(4), nullable=False)
    status: Mapped[int] = mapped_column(TINYINT(1), nullable=False)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)


class DriverJobOrders(Base):
    __tablename__ = 'driver_job_orders'
    __table_args__ = (
        ForeignKeyConstraint(['p2h_id'], ['driver_p2h.id'], name='driver_job_orders_p2h_id_foreign'),
        ForeignKeyConstraint(['user_id'], ['users.id'], name='driver_job_orders_user_id_foreign'),
        Index('driver_job_orders_p2h_id_foreign', 'p2h_id'),
        Index('driver_job_orders_user_id_foreign', 'user_id')
    )

    id: Mapped[int] = mapped_column(BIGINT(20), primary_key=True)
    user_id: Mapped[int] = mapped_column(BIGINT(20), nullable=False)
    status: Mapped[str] = mapped_column(Enum('ASSIGNED', 'ON_THE_WAY_PICKUP', 'PICKED_UP', 'COMPLETED', 'CANCELED'), nullable=False, server_default=text("'ASSIGNED'"))
    p2h_id: Mapped[Optional[int]] = mapped_column(BIGINT(20))
    nama_tamu: Mapped[Optional[str]] = mapped_column(String(255))
    tujuan_perjalanan: Mapped[Optional[str]] = mapped_column(String(255))
    lokasi_jemput: Mapped[Optional[str]] = mapped_column(String(255))
    lokasi_tujuan: Mapped[Optional[str]] = mapped_column(String(255))
    jadwal_jemput: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    waktu_mulai: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    waktu_sampai_tujuan: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    odometer_akhir_tugas: Mapped[Optional[int]] = mapped_column(INTEGER(11))
    foto_odometer_akhir: Mapped[Optional[str]] = mapped_column(String(255))
    keterangan_selesai: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)

    p2h: Mapped[Optional['DriverP2h']] = relationship('DriverP2h', back_populates='driver_job_orders')
    user: Mapped['Users'] = relationship('Users', back_populates='driver_job_orders', passive_deletes=True)


class DriverReimbursements(Base):
    __tablename__ = 'driver_reimbursements'
    __table_args__ = (
        ForeignKeyConstraint(['p2h_id'], ['driver_p2h.id'], name='driver_reimbursements_p2h_id_foreign'),
        Index('driver_reimbursements_p2h_id_foreign', 'p2h_id')
    )

    id: Mapped[int] = mapped_column(BIGINT(20), primary_key=True)
    p2h_id: Mapped[int] = mapped_column(BIGINT(20), nullable=False)
    kategori: Mapped[str] = mapped_column(Enum('TOL', 'PARKIR', 'CUCI', 'TAMBAL_BAN', 'LAINNYA'), nullable=False)
    nominal: Mapped[int] = mapped_column(INTEGER(11), nullable=False)
    status: Mapped[str] = mapped_column(Enum('PENDING', 'PAID', 'REJECTED'), nullable=False, server_default=text("'PENDING'"))
    keterangan: Mapped[Optional[str]] = mapped_column(Text)
    foto_struk: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)

    p2h: Mapped['DriverP2h'] = relationship('DriverP2h', back_populates='driver_reimbursements')


class EmergencyAlerts(Base):
    __tablename__ = 'emergency_alerts'
    __table_args__ = (
        ForeignKeyConstraint(['id_user'], ['users.id'], ondelete='CASCADE', name='emergency_alerts_id_user_foreign'),
        ForeignKeyConstraint(['nik'], ['karyawan.nik'], onupdate='CASCADE', name='emergency_alerts_nik_foreign'),
        Index('emergency_alerts_branch_code_index', 'branch_code'),
        Index('emergency_alerts_id_user_foreign', 'id_user'),
        Index('emergency_alerts_nik_foreign', 'nik')
    )

    id: Mapped[int] = mapped_column(BIGINT(20), primary_key=True)
    id_user: Mapped[int] = mapped_column(BIGINT(20), nullable=False)
    nik: Mapped[str] = mapped_column(String(20), nullable=False)
    alarm_type: Mapped[str] = mapped_column(String(64), nullable=False)
    response_status: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'pending'"))
    branch_code: Mapped[Optional[str]] = mapped_column(CHAR(3))
    location: Mapped[Optional[str]] = mapped_column(Text)
    payload: Mapped[Optional[str]] = mapped_column(LONGTEXT)
    triggered_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    response_message: Mapped[Optional[str]] = mapped_column(Text)
    retry_after: Mapped[Optional[int]] = mapped_column(INTEGER(11))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)

    users: Mapped['Users'] = relationship('Users', back_populates='emergency_alerts', passive_deletes=True)
    karyawan: Mapped['Karyawan'] = relationship('Karyawan', back_populates='emergency_alerts', passive_deletes=True)


t_hari_libur_detail = Table(
    'hari_libur_detail', Base.metadata,
    Column('kode_libur', CHAR(7), nullable=False),
    Column('nik', CHAR(18), nullable=False),
    Column('created_at', TIMESTAMP),
    Column('updated_at', TIMESTAMP),
    ForeignKeyConstraint(['kode_libur'], ['hari_libur.kode_libur'], ondelete='CASCADE', onupdate='CASCADE', name='hari_libur_detail_kode_libur_foreign'),
    Index('hari_libur_detail_kode_libur_foreign', 'kode_libur'),
    Index('hari_libur_detail_nik_foreign', 'nik')
)


class KaryawanDevices(Base):
    __tablename__ = 'karyawan_devices'
    __table_args__ = (
        ForeignKeyConstraint(['nik'], ['karyawan.nik'], ondelete='CASCADE', name='fk_karyawan_devices_nik'),
        Index('idx_nik', 'nik'),
        Index('uniq_token', 'fcm_token', unique=True)
    )

    id: Mapped[int] = mapped_column(BIGINT(20), primary_key=True)
    nik: Mapped[str] = mapped_column(CHAR(18), nullable=False)
    fcm_token: Mapped[str] = mapped_column(Text, nullable=False)
    device_id: Mapped[Optional[str]] = mapped_column(String(191))
    device_type: Mapped[Optional[str]] = mapped_column(String(20), server_default=text("'android'"))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)

    karyawan: Mapped['Karyawan'] = relationship('Karyawan', back_populates='karyawan_devices')


class ModelHasPermissions(Base):
    __tablename__ = 'model_has_permissions'
    __table_args__ = (
        ForeignKeyConstraint(['permission_id'], ['permissions.id'], ondelete='CASCADE', name='model_has_permissions_permission_id_foreign'),
        Index('model_has_permissions_model_id_model_type_index', 'model_id', 'model_type')
    )

    permission_id: Mapped[int] = mapped_column(BIGINT(20), primary_key=True)
    model_type: Mapped[str] = mapped_column(String(255), primary_key=True)
    model_id: Mapped[int] = mapped_column(BIGINT(20), primary_key=True)

    permission: Mapped['Permissions'] = relationship('Permissions', back_populates='model_has_permissions')


class Pengunjung(Base):
    __tablename__ = 'pengunjung'
    __table_args__ = (
        ForeignKeyConstraint(['nik'], ['karyawan.nik'], ondelete='SET NULL', name='pengunjung_nik_foreign'),
        Index('pengunjung_nik_foreign', 'nik'),
        Index('pengunjung_updated_by_foreign', 'updated_by_nik')
    )

    id: Mapped[int] = mapped_column(BIGINT(20), primary_key=True)
    jenis_pengunjung: Mapped[str] = mapped_column(String(255), nullable=False)
    nama: Mapped[str] = mapped_column(String(255), nullable=False)
    foto_ktp: Mapped[Optional[str]] = mapped_column(String(255))
    sub_jenis: Mapped[Optional[str]] = mapped_column(String(255))
    sub_sub_jenis: Mapped[Optional[str]] = mapped_column(String(255))
    nomor_kendaraan: Mapped[Optional[str]] = mapped_column(String(255))
    bertemu_dengan: Mapped[Optional[str]] = mapped_column(String(255))
    keperluan: Mapped[Optional[str]] = mapped_column(Text)
    tanggal: Mapped[Optional[datetime.date]] = mapped_column(Date)
    jam_masuk: Mapped[Optional[datetime.time]] = mapped_column(Time)
    jam_pulang: Mapped[Optional[datetime.time]] = mapped_column(Time)
    updated_by_nik: Mapped[Optional[str]] = mapped_column(String(30))
    nik: Mapped[Optional[str]] = mapped_column(String(30))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)

    karyawan: Mapped[Optional['Karyawan']] = relationship('Karyawan', back_populates='pengunjung')


class PresensiIzin(Base):
    __tablename__ = 'presensi_izin'
    __table_args__ = (
        ForeignKeyConstraint(['nik'], ['karyawan.nik'], ondelete='CASCADE', name='presensi_izin_nik_foreign'),
        Index('presensi_izin_nik_index', 'nik')
    )

    kode_izin: Mapped[str] = mapped_column(CHAR(10), primary_key=True)
    tanggal: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    dari: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    sampai: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    nik: Mapped[str] = mapped_column(CHAR(18), nullable=False)
    keterangan: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(CHAR(1), nullable=False, server_default=text("'0'"))
    keterangan_hrd: Mapped[Optional[str]] = mapped_column(String(255))
    surat_sakit: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)

    karyawan: Mapped['Karyawan'] = relationship('Karyawan', back_populates='presensi_izin')
    presensi_izin_approve: Mapped[list['PresensiIzinApprove']] = relationship('PresensiIzinApprove', back_populates='presensi_izin')


class PresensiIzinabsenApprove(Presensi):
    __tablename__ = 'presensi_izinabsen_approve'
    __table_args__ = (
        ForeignKeyConstraint(['id_presensi'], ['presensi.id'], ondelete='CASCADE', onupdate='CASCADE', name='presensi_izinabsen_approve_id_presensi_foreign'),
        ForeignKeyConstraint(['kode_izin'], ['presensi_izinabsen.kode_izin'], ondelete='CASCADE', onupdate='CASCADE', name='presensi_izinabsen_approve_kode_izin_foreign'),
        Index('presensi_izinabsen_approve_kode_izin_foreign', 'kode_izin')
    )

    id_presensi: Mapped[int] = mapped_column(BIGINT(20), primary_key=True)
    kode_izin: Mapped[str] = mapped_column(CHAR(10), nullable=False)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)

    presensi_izinabsen: Mapped['PresensiIzinabsen'] = relationship('PresensiIzinabsen', back_populates='presensi_izinabsen_approve')


class PresensiIzincutiApprove(Presensi):
    __tablename__ = 'presensi_izincuti_approve'
    __table_args__ = (
        ForeignKeyConstraint(['id_presensi'], ['presensi.id'], ondelete='CASCADE', onupdate='CASCADE', name='presensi_izincuti_approve_id_presensi_foreign'),
        ForeignKeyConstraint(['kode_izin_cuti'], ['presensi_izincuti.kode_izin_cuti'], ondelete='CASCADE', onupdate='CASCADE', name='presensi_izincuti_approve_kode_izin_cuti_foreign'),
        Index('presensi_izincuti_approve_kode_izin_cuti_foreign', 'kode_izin_cuti')
    )

    id_presensi: Mapped[int] = mapped_column(BIGINT(20), primary_key=True)
    kode_izin_cuti: Mapped[str] = mapped_column(CHAR(10), nullable=False)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)

    presensi_izincuti: Mapped['PresensiIzincuti'] = relationship('PresensiIzincuti', back_populates='presensi_izincuti_approve')


class PresensiIzinsakitApprove(Presensi):
    __tablename__ = 'presensi_izinsakit_approve'
    __table_args__ = (
        ForeignKeyConstraint(['id_presensi'], ['presensi.id'], ondelete='CASCADE', onupdate='CASCADE', name='presensi_izinsakit_approve_id_presensi_foreign'),
        ForeignKeyConstraint(['kode_izin_sakit'], ['presensi_izinsakit.kode_izin_sakit'], ondelete='CASCADE', onupdate='CASCADE', name='presensi_izinsakit_approve_kode_izin_sakit_foreign'),
        Index('presensi_izinsakit_approve_kode_izin_sakit_foreign', 'kode_izin_sakit')
    )

    id_presensi: Mapped[int] = mapped_column(BIGINT(20), primary_key=True)
    kode_izin_sakit: Mapped[str] = mapped_column(CHAR(10), nullable=False)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)

    presensi_izinsakit: Mapped['PresensiIzinsakit'] = relationship('PresensiIzinsakit', back_populates='presensi_izinsakit_approve')


class PresensiJamkerjaBydateExtra(Base):
    __tablename__ = 'presensi_jamkerja_bydate_extra'
    __table_args__ = (
        ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL', onupdate='CASCADE', name='presensi_jamkerja_bydate_extra_created_by_foreign'),
        ForeignKeyConstraint(['kode_jam_kerja'], ['presensi_jamkerja.kode_jam_kerja'], onupdate='CASCADE', name='presensi_jamkerja_bydate_extra_kode_jam_kerja_foreign'),
        ForeignKeyConstraint(['nik'], ['karyawan.nik'], onupdate='CASCADE', name='presensi_jamkerja_bydate_extra_nik_foreign'),
        Index('presensi_jamkerja_bydate_extra_created_by_foreign', 'created_by'),
        Index('presensi_jamkerja_bydate_extra_kode_jam_kerja_foreign', 'kode_jam_kerja'),
        Index('uniq_bydate_extra_nik_tanggal', 'nik', 'tanggal', unique=True)
    )

    id: Mapped[int] = mapped_column(BIGINT(20), primary_key=True)
    nik: Mapped[str] = mapped_column(CHAR(18), nullable=False)
    tanggal: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    kode_jam_kerja: Mapped[str] = mapped_column(CHAR(4), nullable=False)
    jenis: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'double_shift'"))
    keterangan: Mapped[Optional[str]] = mapped_column(String(255))
    created_by: Mapped[Optional[int]] = mapped_column(BIGINT(20))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)

    users: Mapped[Optional['Users']] = relationship('Users', back_populates='presensi_jamkerja_bydate_extra')
    presensi_jamkerja: Mapped['PresensiJamkerja'] = relationship('PresensiJamkerja', back_populates='presensi_jamkerja_bydate_extra')
    karyawan: Mapped['Karyawan'] = relationship('Karyawan', back_populates='presensi_jamkerja_bydate_extra')


t_role_has_permissions = Table(
    'role_has_permissions', Base.metadata,
    Column('permission_id', BIGINT(20), primary_key=True),
    Column('role_id', BIGINT(20), primary_key=True),
    ForeignKeyConstraint(['permission_id'], ['permissions.id'], ondelete='CASCADE', name='role_has_permissions_permission_id_foreign'),
    ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='CASCADE', name='role_has_permissions_role_id_foreign'),
    Index('role_has_permissions_role_id_foreign', 'role_id')
)


class SafetyBriefings(Base):
    __tablename__ = 'safety_briefings'
    __table_args__ = (
        ForeignKeyConstraint(['nik'], ['karyawan.nik'], ondelete='CASCADE', onupdate='CASCADE', name='fk_safety_briefing_karyawan'),
        Index('fk_safety_briefing_karyawan', 'nik')
    )

    id: Mapped[int] = mapped_column(BIGINT(20), primary_key=True)
    nik: Mapped[str] = mapped_column(CHAR(18), nullable=False, comment='NIK karyawan dari tabel karyawan')
    keterangan: Mapped[str] = mapped_column(Text, nullable=False, comment='Keterangan atau deskripsi briefing')
    tanggal_jam: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, comment='Tanggal dan jam briefing')
    foto: Mapped[Optional[str]] = mapped_column(String(255), comment='URL atau path foto briefing')
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP, server_default=text('current_timestamp()'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP, server_default=text('current_timestamp() ON UPDATE current_timestamp()'))

    karyawan: Mapped['Karyawan'] = relationship('Karyawan', back_populates='safety_briefings')


class SuratKeluar(Base):
    __tablename__ = 'surat_keluar'
    __table_args__ = (
        ForeignKeyConstraint(['nik_satpam'], ['karyawan.nik'], onupdate='CASCADE', name='fk_surat_keluar_satpam'),
        Index('idx_nik_satpam_keluar', 'nik_satpam')
    )

    id: Mapped[int] = mapped_column(INTEGER(11), primary_key=True)
    nomor_surat: Mapped[str] = mapped_column(String(100), nullable=False)
    tanggal_surat: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    tujuan_surat: Mapped[str] = mapped_column(String(200), nullable=False)
    perihal: Mapped[str] = mapped_column(String(255), nullable=False)
    nik_satpam: Mapped[str] = mapped_column(CHAR(18), nullable=False)
    foto: Mapped[Optional[str]] = mapped_column(String(255))
    foto_penerima: Mapped[Optional[str]] = mapped_column(String(255))
    nik_satpam_pengantar: Mapped[Optional[str]] = mapped_column(CHAR(18))
    nama_penerima: Mapped[Optional[str]] = mapped_column(String(255))
    no_penerima: Mapped[Optional[str]] = mapped_column(String(50))
    status_surat: Mapped[Optional[str]] = mapped_column(Enum('KELUAR', 'DIPROSES', 'SELESAI'), server_default=text("'KELUAR'"))
    tanggal_update: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    status_penerimaan: Mapped[Optional[str]] = mapped_column(Enum('BELUM', 'DITERIMA'), server_default=text("'BELUM'"))
    tanggal_diterima: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)

    karyawan: Mapped['Karyawan'] = relationship('Karyawan', back_populates='surat_keluar')




class SuratMasuk(Base):
    __tablename__ = 'surat_masuk'
    __table_args__ = (
        ForeignKeyConstraint(['nik_satpam'], ['karyawan.nik'], onupdate='CASCADE', name='fk_surat_masuk_satpam'),
        Index('idx_nik_satpam', 'nik_satpam')
    )

    id: Mapped[int] = mapped_column(INTEGER(11), primary_key=True)
    nomor_surat: Mapped[str] = mapped_column(String(100), nullable=False)
    tanggal_surat: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    asal_surat: Mapped[str] = mapped_column(String(200), nullable=False)
    tujuan_surat: Mapped[str] = mapped_column(String(200), nullable=False)
    perihal: Mapped[str] = mapped_column(String(255), nullable=False)
    nik_satpam: Mapped[str] = mapped_column(CHAR(18), nullable=False)
    foto: Mapped[Optional[str]] = mapped_column(String(255))
    nik_satpam_pengantar: Mapped[Optional[str]] = mapped_column(CHAR(18))
    nama_penerima: Mapped[Optional[str]] = mapped_column(String(255))
    no_penerima: Mapped[Optional[str]] = mapped_column(String(13))
    foto_penerima: Mapped[Optional[str]] = mapped_column(String(255))
    status_surat: Mapped[Optional[str]] = mapped_column(Enum('MASUK', 'DIPROSES', 'SELESAI'), server_default=text("'MASUK'"))
    tanggal_update: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    status_penerimaan: Mapped[Optional[str]] = mapped_column(Enum('BELUM', 'DITERIMA'), server_default=text("'BELUM'"))
    tanggal_diterima: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)

    karyawan: Mapped['Karyawan'] = relationship('Karyawan', back_populates='surat_masuk')


class Tamu(Base):
    __tablename__ = 'tamu'
    __table_args__ = (
        ForeignKeyConstraint(['nik_satpam'], ['karyawan.nik'], name='fk_nik_satpam'),
        Index('fk_nik_satpam', 'nik_satpam')
    )

    id_tamu: Mapped[int] = mapped_column(INTEGER(11), primary_key=True)
    nama: Mapped[str] = mapped_column(String(100), nullable=False)
    alamat: Mapped[Optional[str]] = mapped_column(Text)
    jenis_id: Mapped[Optional[str]] = mapped_column(String(50))
    no_telp: Mapped[Optional[str]] = mapped_column(String(20))
    perusahaan: Mapped[Optional[str]] = mapped_column(String(100))
    bertemu_dengan: Mapped[Optional[str]] = mapped_column(String(100))
    dengan_perjanjian: Mapped[Optional[str]] = mapped_column(Enum('YA', 'TIDAK'), server_default=text("'TIDAK'"))
    keperluan: Mapped[Optional[str]] = mapped_column(Text)
    jenis_kendaraan: Mapped[Optional[str]] = mapped_column(Enum('PEJALAN KAKI', 'RODA 2', 'RODA 4'), server_default=text("'PEJALAN KAKI'"))
    no_pol: Mapped[Optional[str]] = mapped_column(String(20))
    foto: Mapped[Optional[str]] = mapped_column(String(255))
    foto_keluar: Mapped[Optional[str]] = mapped_column(String(255))
    barcode_kartu: Mapped[Optional[str]] = mapped_column(String(255))
    jam_masuk: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    jam_keluar: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    nik_satpam: Mapped[Optional[str]] = mapped_column(CHAR(18))
    nik_satpam_keluar: Mapped[Optional[str]] = mapped_column(CHAR(18))

    karyawan: Mapped[Optional['Karyawan']] = relationship('Karyawan', back_populates='tamu')


class Turlalin(Base):
    __tablename__ = 'turlalin'
    __table_args__ = (
        ForeignKeyConstraint(['nik'], ['karyawan.nik'], name='fk_nik_masuk'),
        ForeignKeyConstraint(['nik_keluar'], ['karyawan.nik'], name='fk_nik_keluar'),
        Index('idx_nik', 'nik'),
        Index('idx_nik_keluar', 'nik_keluar')
    )

    id: Mapped[int] = mapped_column(INTEGER(11), primary_key=True)
    nomor_polisi: Mapped[str] = mapped_column(String(20), nullable=False)
    jam_masuk: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    nik: Mapped[str] = mapped_column(CHAR(18), nullable=False)
    keterangan: Mapped[Optional[str]] = mapped_column(Text)
    foto: Mapped[Optional[str]] = mapped_column(String(255))
    jam_keluar: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    nik_keluar: Mapped[Optional[str]] = mapped_column(CHAR(18))
    foto_keluar: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('current_timestamp()'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, server_default=text('current_timestamp() ON UPDATE current_timestamp()'))

    karyawan: Mapped['Karyawan'] = relationship('Karyawan', foreign_keys=[nik], back_populates='turlalin')
    karyawan_: Mapped[Optional['Karyawan']] = relationship('Karyawan', foreign_keys=[nik_keluar], back_populates='turlalin_')


class WalkieLogs(Base):
    __tablename__ = 'walkie_logs'
    __table_args__ = (
        ForeignKeyConstraint(['nik'], ['karyawan.nik'], ondelete='CASCADE', onupdate='CASCADE', name='fk_walkie_logs_karyawan'),
        Index('idx_nik', 'nik'),
        Index('idx_room', 'room')
    )

    id: Mapped[int] = mapped_column(BIGINT(20), primary_key=True)
    nik: Mapped[str] = mapped_column(CHAR(18), nullable=False)
    room: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP, server_default=text('current_timestamp()'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP, server_default=text('current_timestamp() ON UPDATE current_timestamp()'))

    karyawan: Mapped['Karyawan'] = relationship('Karyawan', back_populates='walkie_logs')


class PresensiIzinApprove(Base):
    __tablename__ = 'presensi_izin_approve'
    __table_args__ = (
        ForeignKeyConstraint(['kode_izin'], ['presensi_izin.kode_izin'], ondelete='CASCADE', name='presensi_izin_approve_kode_izin_foreign'),
        Index('presensi_izin_approve_kode_izin_index', 'kode_izin')
    )

    id_presensi: Mapped[int] = mapped_column(BIGINT(20), primary_key=True)
    kode_izin: Mapped[str] = mapped_column(CHAR(10), nullable=False)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)

    presensi_izin: Mapped['PresensiIzin'] = relationship('PresensiIzin', back_populates='presensi_izin_approve')







class PresensiJamkerjaByDeptDetail(Base):
    __tablename__ = 'presensi_jamkerja_bydept_detail'
    __table_args__ = {'extend_existing': True}
    
    kode_jk_dept: Mapped[str] = mapped_column(CHAR(7), primary_key=True)
    hari: Mapped[str] = mapped_column(String(255), primary_key=True)
    kode_jam_kerja: Mapped[str] = mapped_column(CHAR(4))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)


class Violation(Base):
    __tablename__ = 'violations'

    id: Mapped[int] = mapped_column(BIGINT(20), primary_key=True, autoincrement=True)
    nik: Mapped[str] = mapped_column(String(20), ForeignKey('karyawan.nik'), nullable=False)
    tanggal_pelanggaran: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    jenis_pelanggaran: Mapped[str] = mapped_column(Enum('RINGAN', 'SEDANG', 'BERAT'), nullable=False)
    keterangan: Mapped[str] = mapped_column(Text, nullable=False)
    sanksi: Mapped[Optional[str]] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(Enum('OPEN', 'CLOSED', 'SELESAI'), server_default=text("'OPEN'"), nullable=False)
    bukti_foto: Mapped[Optional[str]] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(Enum('MANUAL', 'SYSTEM'), server_default=text("'MANUAL'"), nullable=False)
    violation_type: Mapped[Optional[str]] = mapped_column(String(50)) 
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP, server_default=text('current_timestamp()'))
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP, server_default=text('current_timestamp() ON UPDATE current_timestamp()'))

    karyawan: Mapped['Karyawan'] = relationship('Karyawan', foreign_keys=[nik], back_populates='violations')


class AppFraud(Base):
    __tablename__ = 'app_frauds'

    id: Mapped[int] = mapped_column(BIGINT(20), primary_key=True, autoincrement=True)
    nik: Mapped[str] = mapped_column(String(20), ForeignKey('karyawan.nik'), nullable=False)
    fraud_type: Mapped[str] = mapped_column(String(50), nullable=False) # FAKE_GPS, FORCE_CLOSE, ROOT_DEVICE
    description: Mapped[Optional[str]] = mapped_column(Text)
    timestamp: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP, server_default=text('current_timestamp()'))
    
    karyawan: Mapped['Karyawan'] = relationship('Karyawan', foreign_keys=[nik], back_populates='app_frauds')


class ReminderSettings(Base):
    """
    Konfigurasi reminder yang dikelola admin dari backend.
    Scheduler membaca tabel ini setiap menit untuk menentukan
    apakah perlu mengirim push notification FCM ke user.
    """
    __tablename__ = 'reminder_settings'

    id:             Mapped[int]           = mapped_column(BIGINT(20, unsigned=True), primary_key=True, autoincrement=True)
    type:           Mapped[str]           = mapped_column(String(50), nullable=False)
    label:          Mapped[str]           = mapped_column(String(100), nullable=False, server_default=text("'Pengingat'"))
    message:        Mapped[str]           = mapped_column(String(255), nullable=False)
    minutes_before: Mapped[int]           = mapped_column(SMALLINT(), nullable=False, server_default=text("'30'"))
    target_role:    Mapped[Optional[str]] = mapped_column(String(50))   # satpam|cleaning|driver|NULL=semua
    target_dept:    Mapped[Optional[str]] = mapped_column(String(50))   # kode_dept, NULL=semua
    target_cabang:  Mapped[Optional[str]] = mapped_column(String(50))   # kode_cabang, NULL=semua
    target_shift:   Mapped[Optional[str]] = mapped_column(String(10))   # kode_jam_kerja, NULL=semua
    is_active:      Mapped[int]           = mapped_column(TINYINT(1), nullable=False, server_default=text("'1'"))
    created_at:     Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
    updated_at:     Mapped[Optional[datetime.datetime]] = mapped_column(TIMESTAMP)
