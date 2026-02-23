<?php
require __DIR__.'/vendor/autoload.php';
$app = require_once __DIR__.'/bootstrap/app.php';
$kernel = $app->make(Illuminate\Contracts\Console\Kernel::class);
$kernel->bootstrap();

use App\Models\PatrolSessions;
use Illuminate\Support\Facades\DB;

$session = PatrolSessions::find(8343);
echo "Foto absen DB: " . $session->foto_absen . "\n";
$points = DB::table('patrol_points')
            ->join('patrol_point_master', 'patrol_points.patrol_point_master_id', '=', 'patrol_point_master.id')
            ->where('patrol_points.patrol_session_id', $session->id)
            ->select('patrol_points.*', 'patrol_point_master.nama_titik', 'patrol_point_master.urutan')
            ->orderBy('patrol_point_master.urutan', 'asc')
            ->get();
            
echo "Points count: " . $points->count() . "\n";
