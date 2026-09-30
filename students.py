students:dict[str,str] = {}
faculty:dict[str,str] = {}
exam:dict[str,str] = {}
python_marks:dict[str,str] = {}
results: dict[str, dict[str, float]] = {}
subjects = ['Python', 'SQL', 'Excel', 'Power BI', 'Statistics']

while True:
    print('\tSTUDENT MANAGEMENT SYSTEM')
    print('1. Student Management')
    print('2. Faculty Management')
    print('3. Exam Management')
    print('4. Exit')

    choice = input('Enter your choice: ')

    match choice:
        case '1':
            print('\tStudent Managment')
            print('1. Add Student')
            print('2. View Students')
            print('3. Delete Student')

            student_choice = input('Enter your choice: ')

            match student_choice:
                case '1':
                    student_id = input('Enter student ID: ')
                    student_name = input('Enter student name: ')
                    students[student_id] = student_name
                    print('Student added.')

                case '2':
                    if students:
                        for student_id, student_name in students.items():
                            print(f'{student_id}: {student_name}')
                    else:
                        print('No students added yet.')

                case '3':
                    student_id = input('Enter the student ID to delete: ')
                    if student_id in students:
                        del students[student_id]
                        print('Student deleted.')
                    else:
                        print('Student ID not found.')

                case _:
                    print('Invalid student choice.')
             
                    
                

        case '2':
            print('Faculty Management selected')
            fac=(input('Are you a Teacher:\tYES\tNO'))
            if fac == 'yes':
                print('1.Enter Facutly Name:')
                print('2.Enter View Faculty')
                print('3.Delete faculty')

                faculty_choice = input('Enter your Choice:')

                match faculty_choice:

                    case '1':
                        faculty_id = input('Enter student ID: ')
                        faculty_name = input('Enter student name: ')
                        faculty[faculty_id] = faculty_name
                        print('Student added.')
                    case '2':
                        if faculty:
                            for faculty_name,faculty_id in faculty.items():
                                print(f'{faculty_id}:{faculty_name}')

                        else:
                            print('no faculty added')
                    case'3':
                        faculty_id = input('Enter the student ID to delete: ')
                        if faculty_id in faculty:
                            del faculty[faculty_id]
                            print('faculty deleted.')
                        else:
                            print('Invalid Faculty id')


                    case _:
                        print('Invalid Character')
                
                        





        case '3':
            print('\tExam Management selected')                                     
            print('1. Add Exam')
            print('2. View Exams')
            print('3. Results')
            exam_mgmt = input('Enter Your Selection')
            match exam_mgmt:
                case '1':
                    exam_id = input('Enter exam id:')
                    exam_name = input('Enter Exam Subject Name:')
                    exam[exam_id] = exam_name
                    print('Exam added')
                case '2':
                    if exam:
                        for exam_id,exam_name in exam.items():
                            print(f'{exam_id}:{exam_name}')
                    else:
                        print('No Exam Added')
                           
                case '3':
                    print('\tRESULTS')
                    print('1.Enter Your marks:')
                    print('2.View results:')
                    print('3.calculate percentage')
                    print('4.Calculate Grade')
                    print('5.pass/fail')
                    print('6.Subject-Wise Analysis')
                    print('7.Overall Performace')
                    print('8.Back')
                    results_match = input('Enter Your Choice:')
                    match results_match:
                        case '1':
                            print('\tSelect Your subjects')
                            for subject_number, subject in enumerate(subjects, start=1):
                                print(f'{subject_number}. {subject}')

                            subject_match = input('Choose a subject number: ')
                            if not subject_match.isdigit() or not 1 <= int(subject_match) <= len(subjects):
                                print('Invalid subject choice.')
                            else:
                                subject = subjects[int(subject_match) - 1]
                                student_id = input('Enter student ID: ')
                                if student_id not in students:
                                    print('Student ID not found. Add the student first.')
                                else:
                                    try:
                                        marks = float(input('Enter marks (0-100): '))
                                    except ValueError:
                                        print('Enter marks as a number.')
                                    else:
                                        if 0 <= marks <= 100:
                                            results.setdefault(student_id, {})[subject] = marks
                                            print(f'{subject} marks saved for {students[student_id]}.')
                                        else:
                                            print('Marks must be between 0 and 100.')
                        case '2':
                            student_id = input('Enter student ID: ')
                            student_results = results.get(student_id)
                            if student_results:
                                print(f'Results for {students[student_id]} ({student_id}):')
                                for subject, marks in student_results.items():
                                    print(f'{subject}: {marks:.1f}')
                            else:
                                print('No marks found for that student.')
                        case '3':
                            student_id = input('Enter student ID: ')
                            student_results = results.get(student_id)
                            if student_results:
                                percentage = sum(student_results.values()) / len(student_results)
                                print(f'Percentage: {percentage:.2f}%')
                            else:
                                print('No marks found for that student.')
                        case '4':
                            student_id = input('Enter student ID: ')
                            student_results = results.get(student_id)
                            if student_results:
                                percentage = sum(student_results.values()) / len(student_results)
                                if percentage >= 90:
                                    grade = 'A+'
                                elif percentage >= 80:
                                    grade = 'A'
                                elif percentage >= 70:
                                    grade = 'B'
                                elif percentage >= 60:
                                    grade = 'C'
                                elif percentage >= 50:
                                    grade = 'D'
                                else:
                                    grade = 'F'
                                print(f'Grade: {grade} ({percentage:.2f}%)')
                            else:
                                print('No marks found for that student.')
                        case '5':
                            student_id = input('Enter student ID: ')
                            student_results = results.get(student_id)
                            if student_results:
                                percentage = sum(student_results.values()) / len(student_results)
                                print('Pass' if percentage >= 50 else 'Fail')
                            else:
                                print('No marks found for that student.')
                        case '6':
                            for subject_number, subject in enumerate(subjects, start=1):
                                print(f'{subject_number}. {subject}')
                            subject_match = input('Choose a subject number: ')
                            if not subject_match.isdigit() or not 1 <= int(subject_match) <= len(subjects):
                                print('Invalid subject choice.')
                            else:
                                subject = subjects[int(subject_match) - 1]
                                subject_marks = [
                                    (student_id, student_results[subject])
                                    for student_id, student_results in results.items()
                                    if subject in student_results
                                ]
                                if subject_marks:
                                    for student_id, marks in subject_marks:
                                        print(f'{students[student_id]} ({student_id}): {marks:.1f}')
                                    average = sum(marks for _, marks in subject_marks) / len(subject_marks)
                                    print(f'Class average for {subject}: {average:.2f}')
                                else:
                                    print(f'No marks entered for {subject}.')
                        case '7':
                            if results:
                                all_marks = [
                                    marks
                                    for student_results in results.values()
                                    for marks in student_results.values()
                                ]
                                for student_id, student_results in results.items():
                                    average = sum(student_results.values()) / len(student_results)
                                    print(f'{students[student_id]} ({student_id}): {average:.2f}%')
                                overall_average = sum(all_marks) / len(all_marks)
                                print(f'Overall average: {overall_average:.2f}%')
                            else:
                                print('No marks have been entered.')
                        case '8':
                            pass
                        case _:
                            print('Invalid results choice.')

                case _:
                    print('invalid')    


        case '4':
            print('Exiting the system...')
            break
        case _:
            print('Invalid choice! Please try again.')