Parallel Arrays
Dave Braunschweig

Overview
A group of parallel arrays is a form of implicit data structure that uses multiple arrays to represent a singular array of records. It keeps a separate, homogeneous data array for each field of the record, each having the same number of elements. Then, objects located at the same index in each array are implicitly the fields of a single record.[1]

Discussion
A data structure is a data organization and storage format that enables efficient access and modification. More precisely, a data structure is a collection of data values, the relationships among them, and the functions or operations that can be applied to the data. Data structure options include arrays, linked lists, records, and classes.[2]

Parallel arrays use two or more arrays to represent a collection of data where each corresponding array index is a matching field for a given record. For example, if there are two arrays, one for names and one for ages, the array elements at names[2] and ages[2] would describe the name and age of the third person.

Pseudocode
Function Main
    Declare String Array names[5]
    Declare Integer Array ages[5]
    
    Assign names = ["Lisa", "Michael", "Ashley", "Jacob", "Emily"]
    Assign ages = [49, 48, 26, 19, 16]

    DisplayArrays(names, ages)
End

Function DisplayArrays (String Array names, Integer Array ages)
    Declare Integer index
    
    For index = 0 to Size(array) - 1
        Output names[index] & " is " & ages[index] & " years old"
    End
End
Output
Lisa is 49 years old
Michael is 48 years old
Ashley is 26 years old
Jacob is 19 years old
Emily is 16 years old
Key Terms
parallel array
An implicit data structure that uses multiple arrays to represent a singular array of records.