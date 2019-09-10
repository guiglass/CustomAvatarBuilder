using System;
using System.IO;
using System.IO.Compression;

public static class ZipFile
{
	//it seems 81920 is the default size in CopyTo but this can be changed
	public static void CopyTo(this Stream source, Stream destination, int bufferSize = 81920)
	{
		byte[] array = new byte[bufferSize];
		int count;
		while ((count = source.Read(array, 0, array.Length)) != 0)
		{
			destination.Write(array, 0, count);
		}
	}

	private static string directoryPath = ".\\temp";
	public static void Main()
	{
		DirectoryInfo directorySelected = new DirectoryInfo(directoryPath);
		Compress(directorySelected);

		foreach (FileInfo fileToDecompress in directorySelected.GetFiles("*.gz"))
		{
			Decompress(fileToDecompress);
		}
	}

	public static void Compress(DirectoryInfo directorySelected)
	{
		foreach (FileInfo fileToCompress in directorySelected.GetFiles())
		{
			Compress (fileToCompress);
		}
	}

	public static void Compress(FileInfo fileToCompress) {
		using (FileStream originalFileStream = fileToCompress.OpenRead())
		{
			if ((File.GetAttributes(fileToCompress.FullName) & 
				FileAttributes.Hidden) != FileAttributes.Hidden & fileToCompress.Extension != ".gz")
			{
				using (FileStream compressedFileStream = File.Create(fileToCompress.FullName + ".gz"))
				{
					using (GZipStream compressionStream = new GZipStream(compressedFileStream, 
						CompressionMode.Compress))
					{
						originalFileStream.CopyTo(compressionStream);

					}
				}
				FileInfo info = new FileInfo(directoryPath + Path.DirectorySeparatorChar + fileToCompress.Name + ".gz");
				//Console.WriteLine("Compressed {fileToCompress.Name} from {fileToCompress.Length.ToString()} to {info.Length.ToString()} bytes.");
			}

		}
	}


	public static void Decompress(FileInfo fileToDecompress)
	{
		using (FileStream originalFileStream = fileToDecompress.OpenRead())
		{
			string currentFileName = fileToDecompress.FullName;
			string newFileName = currentFileName.Remove(currentFileName.Length - fileToDecompress.Extension.Length);

			using (FileStream decompressedFileStream = File.Create(newFileName))
			{
				using (GZipStream decompressionStream = new GZipStream(originalFileStream, CompressionMode.Decompress))
				{
					decompressionStream.CopyTo(decompressedFileStream);
					//Console.WriteLine("Decompressed: {fileToDecompress.Name}");
				}
			}
		}
	}
}