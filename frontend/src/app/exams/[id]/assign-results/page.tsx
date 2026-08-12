"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@/lib/auth";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  apiGet,
  getExamStudentsDropdown,
  getSheetsForExam,
  getBatchGradings,
  getBatchesForExam,
  updateSheetMapping,
  AnswerSheet,
  BatchJob,
  Grading,
  StudentDropdownItem,
} from "@/lib/api";

interface Exam {
  id: string;
  title: string;
}

interface SheetWithGrading {
  sheet: AnswerSheet;
  grading: Grading | null;
  assignedStudent: StudentDropdownItem | null;
}

export default function AssignResultsPage() {
  const { user, loading: authLoading } = useAuth();
  const params = useParams();
  const router = useRouter();
  const examId = params.id as string;

  const [exam, setExam] = useState<Exam | null>(null);
  const [sheetsWithGradings, setSheetsWithGradings] = useState<SheetWithGrading[]>([]);
  const [students, setStudents] = useState<StudentDropdownItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | "unassigned">("unassigned");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && user && ["admin", "teacher"].includes(user.role!)) {
      loadData();
    } else if (!authLoading && (!user || !["admin", "teacher"].includes(user.role!))) {
      setLoading(false);
    }
  }, [examId, user, authLoading]);

  const loadData = async () => {
    try {
      setLoading(true);
      const [examData, sheetsData, batchesData, studentsData] = await Promise.all([
        apiGet<Exam>(`/exams/${examId}/`),
        getSheetsForExam(examId),
        getBatchesForExam(examId),
        getExamStudentsDropdown(examId),
      ]);

      setExam(examData);
      setStudents(studentsData);

      const gradingsMap = new Map<string, Grading>();
      for (const batch of batchesData) {
        if (batch.status === "completed") {
          try {
            const gradings = await getBatchGradings(batch.id);
            for (const g of gradings) {
              gradingsMap.set(g.sheet_id, g);
            }
          } catch {
            // skip
          }
        }
      }

      const enriched: SheetWithGrading[] = sheetsData
        .filter((s) => s.status !== "pending_mapping" && s.status !== "skipped")
        .map((sheet) => ({
          sheet,
          grading: gradingsMap.get(sheet.id) || null,
          assignedStudent:
            studentsData.find((st) => st.id === sheet.student_id) || null,
        }));

      setSheetsWithGradings(enriched);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load data");
    } finally {
      setLoading(false);
    }
  };

  const handleAssignStudent = async (sheetId: string, studentId: string) => {
    try {
      setSaving(sheetId);
      await updateSheetMapping(sheetId, { student_id: studentId });
      setSuccess("Student assigned successfully");
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to assign student");
    } finally {
      setSaving(null);
    }
  };

  const filteredSheets =
    filter === "unassigned"
      ? sheetsWithGradings.filter((s) => !s.sheet.student_id)
      : sheetsWithGradings;

  if (authLoading || loading) {
    return <div style={{ textAlign: "center", padding: "2rem" }}>Loading...</div>;
  }

  if (!user || !["admin", "teacher"].includes(user.role!)) {
    return <div>Access denied</div>;
  }

  if (!exam) {
    return <div>Exam not found</div>;
  }

  return (
    <div>
      <div style={{ marginBottom: "2rem" }}>
        <Link href={`/exams/${examId}`} className="btn btn-secondary" style={{ marginBottom: "1rem" }}>
          &larr; Back to Exam
        </Link>
        <h1 className="text-xl" style={{ marginBottom: "0.25rem" }}>
          {exam.title} &mdash; Assign Results to Students
        </h1>
        <p style={{ color: "var(--text-muted)", margin: 0 }}>
          Link graded answer sheets to enrolled students so results appear correctly.
        </p>
      </div>

      {error && (
        <div className="error-message" style={{ marginBottom: "1rem" }}>
          {error}
          <button onClick={() => setError(null)} style={{ float: "right", background: "none", border: "none", color: "inherit", cursor: "pointer" }}>
            &times;
          </button>
        </div>
      )}

      {success && (
        <div style={{ marginBottom: "1rem", padding: "0.75rem 1rem", background: "var(--success-bg)", border: "1px solid var(--success)", borderRadius: "var(--radius-md)", color: "var(--success-text)", fontSize: "0.875rem" }}>
          {success}
          <button onClick={() => setSuccess(null)} style={{ float: "right", background: "none", border: "none", color: "inherit", cursor: "pointer" }}>
            &times;
          </button>
        </div>
      )}

      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem" }}>
        <button
          className={filter === "unassigned" ? "btn btn-primary" : "btn btn-secondary"}
          onClick={() => setFilter("unassigned")}
        >
          Unassigned Only
        </button>
        <button
          className={filter === "all" ? "btn btn-primary" : "btn btn-secondary"}
          onClick={() => setFilter("all")}
        >
          All Graded Sheets
        </button>
      </div>

      <div className="panel" style={{ padding: "1rem" }}>
        {filteredSheets.length === 0 ? (
          <p style={{ color: "var(--text-muted)", textAlign: "center" }}>
            {filter === "unassigned"
              ? "All graded sheets have been assigned to students."
              : "No graded sheets yet. Submit a batch first."}
          </p>
        ) : (
          <div className="table-container">
            <table className="table">
              <thead>
                <tr>
                  <th>Student Name (from sheet)</th>
                  <th>Roll No (from sheet)</th>
                  <th>Score</th>
                  <th>Status</th>
                  <th>Assigned Student</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredSheets.map(({ sheet, grading }) => {
                  const pct =
                    grading && grading.total_max > 0
                      ? Math.round((grading.total_awarded / grading.total_max) * 100)
                      : 0;
                  const scoreColor =
                    pct >= 80 ? "var(--success)" : pct >= 50 ? "var(--warning)" : "var(--error)";

                  return (
                    <tr key={sheet.id}>
                      <td style={{ fontWeight: 500 }}>
                        {sheet.student_name || "Unknown"}
                      </td>
                      <td style={{ color: "var(--text-muted)" }}>
                        {sheet.roll_no || "-"}
                      </td>
                      <td style={{ textAlign: "center" }}>
                        {grading ? (
                          <>
                            <span style={{ fontWeight: 700, color: scoreColor }}>
                              {grading.total_awarded}/{grading.total_max}
                            </span>
                            <span style={{ color: "var(--text-muted)", fontSize: "0.8rem", marginLeft: "0.5rem" }}>
                              ({pct}%)
                            </span>
                          </>
                        ) : (
                          <span style={{ color: "var(--text-muted)" }}>Not graded</span>
                        )}
                      </td>
                      <td>
                        <span
                          className={`node node-${
                            sheet.status === "graded"
                              ? "blue"
                              : sheet.status === "published"
                              ? "green"
                              : "yellow"
                          }`}
                        >
                          {sheet.status}
                        </span>
                      </td>
                      <td>
                        {sheet.student_id ? (
                          <span className="node node-green">
                            {students.find((s) => s.id === sheet.student_id)?.full_name || "Linked"}
                          </span>
                        ) : (
                          <span className="node node-orange">Unassigned</span>
                        )}
                      </td>
                      <td>
                        {grading && !sheet.student_id && (
                          <select
                            className="form-input"
                            style={{ width: "auto", fontSize: "0.8rem" }}
                            defaultValue=""
                            onChange={(e) => {
                              if (e.target.value) {
                                handleAssignStudent(sheet.id, e.target.value);
                              }
                            }}
                            disabled={saving === sheet.id}
                          >
                            <option value="">Assign student...</option>
                            {students.map((s) => (
                              <option key={s.id} value={s.id}>
                                {s.full_name} ({s.roll_no || "no roll"})
                              </option>
                            ))}
                          </select>
                        )}
                        {sheet.student_id && (
                          <Link href={`/exams/${examId}/upload`} className="btn btn-secondary" style={{ fontSize: "0.8rem" }}>
                            Remap
                          </Link>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
